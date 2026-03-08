from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from config import APP_STATE_MAX_BYTES, DB_PATH, SESSION_TTL_DAYS

_WRITE_LOCK = threading.Lock()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc_iso(value: str) -> datetime:
    text = (value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                place TEXT NOT NULL DEFAULT '',
                timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
                assistant_name TEXT NOT NULL DEFAULT 'Ellie',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_state (
                user_id TEXT PRIMARY KEY,
                state_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                is_revoked INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at)")


def db_ready() -> bool:
    try:
        with _connect() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


def create_or_replace_user(
    user_id: str,
    *,
    name: str,
    place: str,
    timezone_name: str,
    assistant_name: str,
) -> None:
    now = utc_now_iso()
    with _WRITE_LOCK, _connect() as conn:
        conn.execute(
            """
            INSERT INTO users (user_id, name, place, timezone, assistant_name, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                name=excluded.name,
                place=excluded.place,
                timezone=excluded.timezone,
                assistant_name=excluded.assistant_name,
                updated_at=excluded.updated_at
            """,
            (user_id, name, place, timezone_name, assistant_name, now, now),
        )


def get_user(user_id: str) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT user_id, name, place, timezone, assistant_name, created_at, updated_at
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def save_app_state(user_id: str, state: Dict[str, Any]) -> None:
    encoded = json.dumps(state, ensure_ascii=False)
    if len(encoded.encode("utf-8")) > APP_STATE_MAX_BYTES:
        raise ValueError("App state too large")

    now = utc_now_iso()
    with _WRITE_LOCK, _connect() as conn:
        conn.execute(
            """
            INSERT INTO app_state (user_id, state_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                state_json=excluded.state_json,
                updated_at=excluded.updated_at
            """,
            (user_id, encoded, now),
        )


def get_app_state(user_id: str) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT state_json FROM app_state WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    if not row:
        return None
    return json.loads(row["state_json"])


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_session(user_id: str, *, ttl_days: int = SESSION_TTL_DAYS) -> Dict[str, str]:
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    now = utc_now()
    expires_at = (now + timedelta(days=ttl_days)).replace(microsecond=0)
    now_iso = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    expires_iso = expires_at.isoformat().replace("+00:00", "Z")

    with _WRITE_LOCK, _connect() as conn:
        conn.execute(
            """
            INSERT INTO sessions (token_hash, user_id, created_at, updated_at, expires_at, is_revoked)
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            (token_hash, user_id, now_iso, now_iso, expires_iso),
        )

    return {
        "access_token": raw_token,
        "expires_at": expires_iso,
    }


def get_session_by_token(raw_token: str) -> Optional[Dict[str, Any]]:
    token_hash = _hash_token(raw_token)
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT token_hash, user_id, created_at, updated_at, expires_at, is_revoked
            FROM sessions
            WHERE token_hash = ?
            """,
            (token_hash,),
        ).fetchone()
    return dict(row) if row else None


def touch_session(raw_token: str) -> None:
    token_hash = _hash_token(raw_token)
    now_iso = utc_now_iso()
    with _WRITE_LOCK, _connect() as conn:
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE token_hash = ?",
            (now_iso, token_hash),
        )


def revoke_session(raw_token: str) -> None:
    token_hash = _hash_token(raw_token)
    with _WRITE_LOCK, _connect() as conn:
        conn.execute(
            "UPDATE sessions SET is_revoked = 1 WHERE token_hash = ?",
            (token_hash,),
        )


def revoke_all_sessions_for_user(user_id: str) -> None:
    with _WRITE_LOCK, _connect() as conn:
        conn.execute(
            "UPDATE sessions SET is_revoked = 1 WHERE user_id = ?",
            (user_id,),
        )


def rotate_session(raw_token: str, *, ttl_days: int = SESSION_TTL_DAYS) -> Optional[Dict[str, str]]:
    session = get_session_by_token(raw_token)
    if not session:
        return None

    if int(session.get("is_revoked") or 0) == 1:
        return None

    expires_at = parse_utc_iso(str(session["expires_at"]))
    if expires_at <= utc_now():
        return None

    user_id = str(session["user_id"])

    with _WRITE_LOCK:
        revoke_session(raw_token)
        new_session = create_session(user_id, ttl_days=ttl_days)

    return {
        "user_id": user_id,
        "access_token": new_session["access_token"],
        "expires_at": new_session["expires_at"],
    }


def prune_expired_sessions() -> int:
    now_iso = utc_now_iso()
    with _WRITE_LOCK, _connect() as conn:
        cur = conn.execute(
            "DELETE FROM sessions WHERE expires_at <= ? OR is_revoked = 1",
            (now_iso,),
        )
        return int(cur.rowcount or 0)