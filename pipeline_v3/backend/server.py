from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

from fastapi import FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from config import (
    ACCESS_TOKEN_TTL_MINUTES,
    API_CORS_ORIGINS,
    API_DOCS_ENABLED,
    API_KEY,
    API_RATE_LIMIT_REQUESTS,
    API_RATE_LIMIT_WINDOW_SECONDS,
    APP_NAME,
    DEBUG,
    LOG_LEVEL,
    MAX_AUDIO_UPLOAD_BYTES,
    MAX_MESSAGE_CHARS,
    OPENAI_API_KEY,
    OPENAI_MAX_RETRIES,
    OPENAI_MODEL,
    OPENAI_TIMEOUT,
    PIPELINE_VERSION,
    REFRESH_TOKEN_TTL_DAYS,
)
from db import (
    create_or_replace_user,
    create_session_pair,
    db_ready,
    get_app_state as db_get_app_state,
    get_session_by_token,
    get_user as db_get_user,
    init_db,
    parse_utc_iso,
    prune_expired_sessions,
    revoke_all_sessions_for_user,
    revoke_session,
    rotate_refresh_session,
    save_app_state as db_save_app_state,
    touch_session,
)
from main_pipeline import PersonaTamilPipeline
from stage_behaviour_questions import BehaviourQuestionnaire, QUESTIONS

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(APP_NAME)

app = FastAPI(
    title="Persona Tamil Mobile API",
    version=PIPELINE_VERSION,
    docs_url="/docs" if API_DOCS_ENABLED else None,
    redoc_url="/redoc" if API_DOCS_ENABLED else None,
    openapi_url="/openapi.json" if API_DOCS_ENABLED else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=API_CORS_ORIGINS or [],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Request-Id"],
)

behaviour = BehaviourQuestionnaire()
PIPELINE_CACHE: Dict[str, PersonaTamilPipeline] = {}
PIPELINE_CACHE_LOCK = threading.RLock()

DATA_ROOT = Path(__file__).resolve().parent / "data"
DATA_ROOT.mkdir(parents=True, exist_ok=True)

openai_client = None
if OPENAI_API_KEY and OpenAI is not None:
    openai_client = OpenAI(
        api_key=OPENAI_API_KEY,
        timeout=OPENAI_TIMEOUT,
        max_retries=OPENAI_MAX_RETRIES,
    )


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str = Field(..., min_length=3, max_length=80)
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_CHARS)


class SaveProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answers: Dict[str, Any]


class ProfileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    exists: bool
    profile: Optional[Dict[str, Any]] = None


class CreateUserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=120)
    place: Optional[str] = Field(default=None, max_length=120)
    timezone: str = Field(default="Asia/Kolkata", min_length=1, max_length=64)
    assistant_name: str = Field(default="Ellie", min_length=1, max_length=60)


class DailyRoutineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    wake_time: str = Field(..., min_length=5, max_length=5)
    sleep_time: str = Field(..., min_length=5, max_length=5)
    work_start: Optional[str] = Field(default=None, max_length=5)
    work_end: Optional[str] = Field(default=None, max_length=5)
    daily_habits: Optional[str] = Field(default=None, max_length=1000)


class ParseDatetimeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(..., min_length=1, max_length=500)
    timezone: str = Field(default="Asia/Kolkata", min_length=1, max_length=64)
    now_iso: Optional[str] = Field(default=None, max_length=64)


class PersonalityAnswersIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answers: Dict[str, Any]


class SessionIssueResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    access_token: str
    access_expires_at: str
    refresh_token: str
    refresh_expires_at: str
    token_type: str
    user_id: str


USER_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{3,80}$")
HHMM_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def sanitize_user_id(user_id: str) -> str:
    value = str(user_id or "").strip()
    if not USER_ID_RE.fullmatch(value):
        raise HTTPException(status_code=400, detail="Invalid user_id")
    return value


def validate_hhmm(v: str) -> None:
    if not HHMM_RE.match(str(v or "").strip()):
        raise HTTPException(status_code=400, detail=f"Invalid time format: {v}")


def normalize_optional(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    value = str(v).strip()
    return value if value else None


def get_pipeline(user_id: str) -> PersonaTamilPipeline:
    user_id = sanitize_user_id(user_id)
    with PIPELINE_CACHE_LOCK:
        if user_id not in PIPELINE_CACHE:
            PIPELINE_CACHE[user_id] = PersonaTamilPipeline(user_id=user_id)
        return PIPELINE_CACHE[user_id]


def reset_pipeline(user_id: str) -> None:
    user_id = sanitize_user_id(user_id)
    with PIPELINE_CACHE_LOCK:
        PIPELINE_CACHE.pop(user_id, None)


def try_parse_json(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return value
    try:
        return json.loads(text)
    except Exception:
        return value


def normalize_pipeline_result(result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "pipeline_version": result.get("pipeline_version", ""),
        "raw_english": result.get("raw_english", ""),
        "remodeled_english": result.get("remodeled_english", ""),
        "tamil_text": result.get("tamil_text", ""),
        "theni_tamil_text": result.get("theni_tamil_text", ""),
        "direct_answer_source": result.get("direct_answer_source", ""),
        "direct_answer_confidence": result.get("direct_answer_confidence", ""),
        "predicted_label": result.get("predicted_label", ""),
        "risk_level": result.get("risk_level", ""),
        "route_taken": result.get("route_taken", ""),
        "cache_hit": result.get("cache_hit", "false"),
        "stage_notes": try_parse_json(result.get("stage_notes", "[]")),
        "core_meta": try_parse_json(result.get("core_meta", "{}")),
        "remodel_meta": try_parse_json(result.get("remodel_meta", "{}")),
        "review_meta": try_parse_json(result.get("review_meta", "{}")),
        "translation_meta": try_parse_json(result.get("translation_meta", "{}")),
        "timings_ms": try_parse_json(result.get("timings_ms", "{}")),
    }


def load_app_state(user_id: str) -> Dict[str, Any]:
    user_id = sanitize_user_id(user_id)
    state = db_get_app_state(user_id)
    if state:
        return state

    user = db_get_user(user_id)
    profile = {
        "name": user["name"] if user else "",
        "place": user["place"] if user else "",
        "timezone": user["timezone"] if user else "Asia/Kolkata",
        "assistant_name": user["assistant_name"] if user else "Ellie",
    }

    return {
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "profile": profile,
        "daily_routine": {
            "wake_time": "07:30",
            "sleep_time": "23:30",
            "work_start": "09:30",
            "work_end": "18:30",
            "daily_habits": "",
        },
    }


def save_app_state(user_id: str, state: Dict[str, Any]) -> None:
    user_id = sanitize_user_id(user_id)
    try:
        db_save_app_state(user_id, state)
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc


def default_answers_from_user_and_routine(
    user_profile: Dict[str, Any],
    daily_routine: Dict[str, Any],
) -> Dict[str, Any]:
    habits_text = str(daily_routine.get("daily_habits") or "").lower()

    hobbies = []
    if "music" in habits_text:
        hobbies.append("music")
    if "movie" in habits_text:
        hobbies.append("movies")
    if "read" in habits_text:
        hobbies.append("reading")
    if "cook" in habits_text:
        hobbies.append("cooking")
    if "travel" in habits_text:
        hobbies.append("travel")
    if not hobbies:
        hobbies = ["music"]

    return {
        "age_group": "26-35",
        "gender_context": "prefer_not_to_say",
        "life_stage": "none_of_these",
        "food_preference": "mixed_flexible",
        "health_conditions": ["none"],
        "food_caution": "no_special_caution",
        "daily_activity": "moderate_walks",
        "sleep_pattern": "average",
        "personality_style": "practical",
        "stress_support": "step_by_step_plan",
        "communication_tone": "friendly_casual",
        "answer_length": "medium",
        "hobbies": hobbies[:3],
        "main_goal": "career_or_business",
        "family_role": "working_professional",
    }


def build_profile_from_answers(
    user_id: str,
    answers: Dict[str, Any],
    existing_profile: Optional[Dict[str, Any]] = None,
    app_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    behaviour_rules = behaviour._derive_behaviour_rules(answers)
    personality_rag = behaviour._infer_personality_rag_from_answers(answers)

    profile = {
        "profile_version": "app_created",
        "user_id": sanitize_user_id(user_id),
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "answers": answers,
        "behaviour_rules": behaviour_rules,
        "rag_personality_hints": personality_rag,
        "app_profile": (app_state or {}).get("profile", {}),
        "daily_routine": (app_state or {}).get("daily_routine", {}),
    }

    if existing_profile:
        profile["created_at"] = existing_profile.get("created_at", profile["created_at"])

    return behaviour._upgrade_profile(profile)


def ensure_pipeline_profile_exists(user_id: str) -> Dict[str, Any]:
    user_id = sanitize_user_id(user_id)
    state = load_app_state(user_id)

    if behaviour.profile_exists(user_id):
        profile = behaviour.load_profile(user_id)

        changed = False
        if profile.get("app_profile") != state.get("profile", {}):
            profile["app_profile"] = state.get("profile", {})
            changed = True
        if profile.get("daily_routine") != state.get("daily_routine", {}):
            profile["daily_routine"] = state.get("daily_routine", {})
            changed = True

        if changed:
            behaviour.save_profile(user_id, profile)
            reset_pipeline(user_id)
            profile = behaviour.load_profile(user_id)

        return profile

    answers = default_answers_from_user_and_routine(
        state.get("profile", {}),
        state.get("daily_routine", {}),
    )
    profile = build_profile_from_answers(user_id, answers, app_state=state)
    behaviour.save_profile(user_id, profile)
    reset_pipeline(user_id)
    return profile


def require_openai() -> Any:
    if openai_client is None:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY is missing or OpenAI client is unavailable.",
        )
    return openai_client


def parse_datetime_with_llm(text: str, timezone_name: str, now_iso: Optional[str]) -> Dict[str, Any]:
    client = require_openai()
    now_iso = now_iso or datetime.now(timezone.utc).isoformat()

    prompt = f"""
You convert natural language time into JSON.

Input:
- timezone: {timezone_name}
- now_iso: {now_iso}
- text: {text}

Return ONLY valid JSON:
{{
  "iso": "YYYY-MM-DDTHH:MM:SS" or null,
  "human": "short readable summary",
  "confidence": 0.0
}}

Rules:
- If the user says tomorrow morning and no exact minute, choose a reasonable exact time.
- Assume the given timezone.
- If unclear, set iso to null and confidence below 0.35.
"""

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You are a strict datetime parser."},
            {"role": "user", "content": prompt},
        ],
    )

    content = response.choices[0].message.content or "{}"
    data = json.loads(content)
    return {
        "iso": data.get("iso"),
        "human": data.get("human") or "",
        "confidence": float(data.get("confidence") or 0.0),
    }


def generate_daily_checkins_with_llm(user_id: str) -> Dict[str, Any]:
    state = load_app_state(user_id)
    user_profile = state.get("profile", {})
    routine = state.get("daily_routine", {}) or {}

    if not routine.get("wake_time") or not routine.get("sleep_time"):
        raise HTTPException(status_code=400, detail="Daily routine not set.")

    client = require_openai()

    prompt = f"""
Generate 4 smart daily check-ins for this user.

User:
- name: {user_profile.get("name", "User")}
- place: {user_profile.get("place", "")}
- timezone: {user_profile.get("timezone", "Asia/Kolkata")}

Routine:
- wake_time: {routine.get("wake_time")}
- sleep_time: {routine.get("sleep_time")}
- work_start: {routine.get("work_start")}
- work_end: {routine.get("work_end")}
- daily_habits: {routine.get("daily_habits", "")}

Return ONLY JSON:
{{
  "checkins": [
    {{
      "title": "string",
      "when": "HH:MM",
      "message": "string"
    }}
  ]
}}

Rules:
- Respect wake/sleep bounds.
- Keep messages short and human.
- Use gentle productivity / wellness reminders.
"""

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You generate routine-aware checkins."},
            {"role": "user", "content": prompt},
        ],
    )

    content = response.choices[0].message.content or '{"checkins":[]}'
    data = json.loads(content)
    checkins = data.get("checkins", [])
    if not isinstance(checkins, list):
        checkins = []

    cleaned = []
    for item in checkins:
        when = str(item.get("when", "")).strip()
        title = str(item.get("title", "")).strip() or "Check-in"
        message = str(item.get("message", "")).strip() or title
        try:
            validate_hhmm(when)
            cleaned.append({"title": title, "when": when, "message": message})
        except Exception:
            continue

    cleaned.sort(key=lambda x: x["when"])
    return {"checkins": cleaned[:8]}


def _extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    token = parts[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return token


def _is_admin_api_key(x_api_key: Optional[str]) -> bool:
    return bool(API_KEY and x_api_key and x_api_key == API_KEY)


def require_auth_user(
    *,
    expected_user_id: Optional[str] = None,
    authorization: Optional[str],
    x_api_key: Optional[str],
) -> Optional[str]:
    if _is_admin_api_key(x_api_key):
        return expected_user_id

    raw_token = _extract_bearer_token(authorization)
    if not raw_token:
        raise HTTPException(status_code=401, detail="Authentication required")

    session = get_session_by_token(raw_token)
    if not session or int(session.get("is_revoked") or 0) == 1:
        raise HTTPException(status_code=401, detail="Invalid session")

    if str(session.get("token_type")) != "access":
        raise HTTPException(status_code=401, detail="Access token required")

    expires_at = parse_utc_iso(str(session["expires_at"]))
    if expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")

    authed_user_id = str(session["user_id"])
    if expected_user_id and authed_user_id != sanitize_user_id(expected_user_id):
        raise HTTPException(status_code=403, detail="Forbidden")

    touch_session(raw_token)
    return authed_user_id


class InMemoryRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._events: dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str) -> tuple[bool, int]:
        now = time.time()
        with self._lock:
            events = self._events[key]
            while events and (now - events[0]) > self.window_seconds:
                events.popleft()

            if len(events) >= self.max_requests:
                retry_after = max(1, int(self.window_seconds - (now - events[0])))
                return False, retry_after

            events.append(now)
            return True, 0


rate_limiter = InMemoryRateLimiter(
    max_requests=API_RATE_LIMIT_REQUESTS,
    window_seconds=API_RATE_LIMIT_WINDOW_SECONDS,
)


@app.middleware("http")
async def add_request_context(request: Request, call_next):
    start = time.perf_counter()
    request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    request.state.request_id = request_id

    client_host = request.client.host if request.client else "unknown"
    auth_hint = request.headers.get("Authorization") or request.headers.get("X-API-Key") or ""
    limiter_key = f"{client_host}:{request.url.path}:{auth_hint[:24]}"

    allowed, retry_after = rate_limiter.hit(limiter_key)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests", "request_id": request_id},
            headers={"Retry-After": str(retry_after), "X-Request-Id": request_id},
        )

    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled server error request_id=%s path=%s", request_id, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "request_id": request_id},
            headers={"X-Request-Id": request_id},
        )

    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["X-Request-Id"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"

    logger.info(
        "request_id=%s method=%s path=%s status=%s duration_ms=%s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", "")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "request_id": request_id},
        headers={"X-Request-Id": request_id} if request_id else None,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", "")
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation error",
            "errors": exc.errors(),
            "request_id": request_id,
        },
        headers={"X-Request-Id": request_id} if request_id else None,
    )


@app.get("/")
def root() -> Dict[str, str]:
    return {
        "status": "ok",
        "service": APP_NAME,
        "version": PIPELINE_VERSION,
    }


@app.get("/health")
def health_root() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> Dict[str, Any]:
    return {
        "status": "ready",
        "service": APP_NAME,
        "version": PIPELINE_VERSION,
        "openai_configured": bool(OPENAI_API_KEY and openai_client is not None),
        "db_ready": db_ready(),
    }


@app.post("/auth/refresh", response_model=SessionIssueResponse)
def refresh_session(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    raw_refresh_token = _extract_bearer_token(authorization)
    if not raw_refresh_token:
        raise HTTPException(status_code=401, detail="Authentication required")

    rotated = rotate_refresh_session(
        raw_refresh_token,
        access_ttl_minutes=ACCESS_TOKEN_TTL_MINUTES,
        refresh_ttl_days=REFRESH_TOKEN_TTL_DAYS,
    )
    if not rotated:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    return {
        "access_token": rotated["access_token"],
        "access_expires_at": rotated["access_expires_at"],
        "refresh_token": rotated["refresh_token"],
        "refresh_expires_at": rotated["refresh_expires_at"],
        "token_type": "bearer",
        "user_id": rotated["user_id"],
    }


@app.post("/auth/logout")
def logout_session(authorization: Optional[str] = Header(default=None)) -> Dict[str, str]:
    raw_token = _extract_bearer_token(authorization)
    if not raw_token:
        raise HTTPException(status_code=401, detail="Authentication required")

    session = get_session_by_token(raw_token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")

    revoke_session(raw_token)
    return {"message": "Logged out successfully"}


@app.post("/auth/logout-all")
def logout_all_sessions(authorization: Optional[str] = Header(default=None)) -> Dict[str, str]:
    raw_token = _extract_bearer_token(authorization)
    if not raw_token:
        raise HTTPException(status_code=401, detail="Authentication required")

    session = get_session_by_token(raw_token)
    if not session or int(session.get("is_revoked") or 0) == 1:
        raise HTTPException(status_code=401, detail="Invalid session")

    expires_at = parse_utc_iso(str(session["expires_at"]))
    if expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")

    user_id = str(session["user_id"])
    revoke_all_sessions_for_user(user_id)
    return {"message": "Logged out from all sessions"}


@app.get("/api/questions")
def get_questions() -> Dict[str, List[Dict[str, Any]]]:
    return {"questions": QUESTIONS}


@app.get("/personality/questions")
def get_personality_questions() -> Dict[str, Any]:
    return {"version": 1, "questions": QUESTIONS}


@app.post("/users")
def create_user(payload: CreateUserRequest) -> Dict[str, Any]:
    try:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        create_or_replace_user(
            user_id,
            name=payload.name.strip(),
            place=(payload.place or "").strip(),
            timezone_name=payload.timezone.strip() or "Asia/Kolkata",
            assistant_name=payload.assistant_name.strip() or "Ellie",
        )

        state = {
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "profile": {
                "name": payload.name.strip(),
                "place": (payload.place or "").strip(),
                "timezone": payload.timezone.strip() or "Asia/Kolkata",
                "assistant_name": payload.assistant_name.strip() or "Ellie",
            },
            "daily_routine": {
                "wake_time": "07:30",
                "sleep_time": "23:30",
                "work_start": "09:30",
                "work_end": "18:30",
                "daily_habits": "",
            },
        }
        save_app_state(user_id, state)
        ensure_pipeline_profile_exists(user_id)

        session_pair = create_session_pair(
            user_id,
            access_ttl_minutes=ACCESS_TOKEN_TTL_MINUTES,
            refresh_ttl_days=REFRESH_TOKEN_TTL_DAYS,
        )

        return {
            "id": user_id,
            "name": state["profile"]["name"],
            "place": state["profile"]["place"],
            "timezone": state["profile"]["timezone"],
            "assistant_name": state["profile"]["assistant_name"],
            "access_token": session_pair["access_token"],
            "access_expires_at": session_pair["access_expires_at"],
            "refresh_token": session_pair["refresh_token"],
            "refresh_expires_at": session_pair["refresh_expires_at"],
            "token_type": "bearer",
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to create user")
        raise HTTPException(status_code=500, detail=f"Failed to create user: {exc}")


@app.get("/users/{user_id}")
def get_user(
    user_id: str,
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    user_id = sanitize_user_id(user_id)
    require_auth_user(expected_user_id=user_id, authorization=authorization, x_api_key=x_api_key)

    state = load_app_state(user_id)
    profile = state.get("profile", {})
    return {
        "id": user_id,
        "name": profile.get("name", ""),
        "place": profile.get("place", ""),
        "timezone": profile.get("timezone", "Asia/Kolkata"),
        "assistant_name": profile.get("assistant_name", "Ellie"),
    }


@app.get("/api/profile/{user_id}", response_model=ProfileResponse)
def get_profile(
    user_id: str,
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None),
) -> ProfileResponse:
    user_id = sanitize_user_id(user_id)
    require_auth_user(expected_user_id=user_id, authorization=authorization, x_api_key=x_api_key)

    try:
        if not behaviour.profile_exists(user_id):
            ensure_pipeline_profile_exists(user_id)
        profile = behaviour.load_profile(user_id)
        return ProfileResponse(exists=True, profile=profile)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to load profile user_id=%s", user_id)
        raise HTTPException(status_code=500, detail=f"Failed to load profile: {exc}")


@app.post("/api/profile/{user_id}")
def save_profile(
    user_id: str,
    payload: SaveProfileRequest,
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    user_id = sanitize_user_id(user_id)
    require_auth_user(expected_user_id=user_id, authorization=authorization, x_api_key=x_api_key)

    try:
        state = load_app_state(user_id)
        existing = behaviour.load_profile(user_id) if behaviour.profile_exists(user_id) else None
        profile = build_profile_from_answers(
            user_id,
            payload.answers or {},
            existing_profile=existing,
            app_state=state,
        )
        behaviour.save_profile(user_id, profile)
        reset_pipeline(user_id)

        return {
            "message": "Profile saved successfully",
            "profile": profile,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to save profile user_id=%s", user_id)
        raise HTTPException(status_code=500, detail=f"Failed to save profile: {exc}")


@app.post("/api/profile/{user_id}/reset")
def reset_profile(
    user_id: str,
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None),
) -> Dict[str, str]:
    user_id = sanitize_user_id(user_id)
    require_auth_user(expected_user_id=user_id, authorization=authorization, x_api_key=x_api_key)

    try:
        path = behaviour._profile_path(user_id)
        if path.exists():
            path.unlink()
        reset_pipeline(user_id)
        return {"message": "Profile reset successfully"}
    except Exception as exc:
        logger.exception("Failed to reset profile user_id=%s", user_id)
        raise HTTPException(status_code=500, detail=f"Failed to reset profile: {exc}")


@app.post("/api/chat")
def chat(
    payload: ChatRequest,
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    user_id = sanitize_user_id(payload.user_id)
    require_auth_user(expected_user_id=user_id, authorization=authorization, x_api_key=x_api_key)

    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    try:
        ensure_pipeline_profile_exists(user_id)
        pipeline = get_pipeline(user_id)
        result = pipeline.run(message)
        return {
            "user_id": user_id,
            "message": message,
            "result": normalize_pipeline_result(result),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Pipeline failed user_id=%s", user_id)
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {exc}")


@app.get("/users/{user_id}/daily-routine")
def get_daily_routine(
    user_id: str,
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    user_id = sanitize_user_id(user_id)
    require_auth_user(expected_user_id=user_id, authorization=authorization, x_api_key=x_api_key)

    state = load_app_state(user_id)
    routine = state.get("daily_routine", {})
    return {"user_id": user_id, **routine}


@app.put("/users/{user_id}/daily-routine")
def upsert_daily_routine(
    user_id: str,
    payload: DailyRoutineIn,
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    user_id = sanitize_user_id(user_id)
    require_auth_user(expected_user_id=user_id, authorization=authorization, x_api_key=x_api_key)

    validate_hhmm(payload.wake_time)
    validate_hhmm(payload.sleep_time)

    work_start = normalize_optional(payload.work_start)
    work_end = normalize_optional(payload.work_end)
    if work_start:
        validate_hhmm(work_start)
    if work_end:
        validate_hhmm(work_end)

    state = load_app_state(user_id)
    state["daily_routine"] = {
        "wake_time": payload.wake_time.strip(),
        "sleep_time": payload.sleep_time.strip(),
        "work_start": work_start,
        "work_end": work_end,
        "daily_habits": normalize_optional(payload.daily_habits) or "",
    }
    save_app_state(user_id, state)
    ensure_pipeline_profile_exists(user_id)
    return {"user_id": user_id, **state["daily_routine"]}


@app.post("/users/{user_id}/questionnaire")
def save_mobile_questionnaire(
    user_id: str,
    payload: Dict[str, Any],
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    user_id = sanitize_user_id(user_id)
    require_auth_user(expected_user_id=user_id, authorization=authorization, x_api_key=x_api_key)

    raw = payload.get("payload", payload)

    mapped = DailyRoutineIn(
        wake_time=str(raw.get("wake") or raw.get("wake_time") or "07:30"),
        sleep_time=str(raw.get("sleep") or raw.get("sleep_time") or "23:30"),
        work_start=raw.get("workStart") or raw.get("work_start"),
        work_end=raw.get("workEnd") or raw.get("work_end"),
        daily_habits=raw.get("dailyHabits") or raw.get("daily_habits"),
    )
    return upsert_daily_routine(
        user_id,
        mapped,
        authorization=authorization,
        x_api_key=x_api_key,
    )


@app.get("/users/{user_id}/personality")
def get_personality(
    user_id: str,
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    user_id = sanitize_user_id(user_id)
    require_auth_user(expected_user_id=user_id, authorization=authorization, x_api_key=x_api_key)

    ensure_pipeline_profile_exists(user_id)
    profile = behaviour.load_profile(user_id)
    return {
        "answers": profile.get("answers", {}),
        "summary": profile.get("profile_summary", ""),
    }


@app.post("/users/{user_id}/personality")
def save_personality_answers(
    user_id: str,
    payload: PersonalityAnswersIn,
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    user_id = sanitize_user_id(user_id)
    require_auth_user(expected_user_id=user_id, authorization=authorization, x_api_key=x_api_key)

    state = load_app_state(user_id)
    existing = behaviour.load_profile(user_id) if behaviour.profile_exists(user_id) else None
    profile = build_profile_from_answers(
        user_id=user_id,
        answers=payload.answers or {},
        existing_profile=existing,
        app_state=state,
    )
    behaviour.save_profile(user_id, profile)
    reset_pipeline(user_id)
    return {"ok": True, "profile": profile}


@app.post("/users/{user_id}/generate-daily-checkins")
def generate_daily_checkins(
    user_id: str,
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    user_id = sanitize_user_id(user_id)
    require_auth_user(expected_user_id=user_id, authorization=authorization, x_api_key=x_api_key)

    try:
        return generate_daily_checkins_with_llm(user_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to generate daily check-ins user_id=%s", user_id)
        raise HTTPException(status_code=500, detail=f"Failed to generate daily check-ins: {exc}")


@app.post("/parse-datetime")
def parse_datetime(
    payload: ParseDatetimeRequest,
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    require_auth_user(expected_user_id=None, authorization=authorization, x_api_key=x_api_key)

    try:
        return parse_datetime_with_llm(payload.text, payload.timezone, payload.now_iso)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to parse datetime")
        raise HTTPException(status_code=500, detail=f"Failed to parse datetime: {exc}")


@app.post("/transcribe-and-analyze")
async def transcribe_and_analyze(
    file: UploadFile = File(...),
    user_id: Optional[str] = Query(default=None),
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    client = require_openai()
    final_user_id = sanitize_user_id(user_id or "guest_user")
    require_auth_user(expected_user_id=final_user_id, authorization=authorization, x_api_key=x_api_key)

    tmp_path: Optional[str] = None
    suffix = os.path.splitext(file.filename or "")[-1] or ".m4a"

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            total_bytes = 0
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > MAX_AUDIO_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Audio file too large")
                tmp.write(chunk)
            tmp_path = tmp.name

        with open(tmp_path, "rb") as audio_file:
            transcript_obj = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="ta",
                response_format="json",
            )

        transcript_text = getattr(transcript_obj, "text", "") or ""
        transcript_text = transcript_text.strip()
        if not transcript_text:
            raise HTTPException(status_code=400, detail="Could not transcribe audio.")

        ensure_pipeline_profile_exists(final_user_id)
        pipeline = get_pipeline(final_user_id)
        result = pipeline.run(transcript_text)

        return {
            "user_id": final_user_id,
            "message": transcript_text,
            "result": normalize_pipeline_result(result),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Voice pipeline failed user_id=%s", final_user_id)
        raise HTTPException(status_code=500, detail=f"Voice pipeline failed: {exc}")
    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except Exception:
                pass


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    deleted = prune_expired_sessions()
    logger.info(
        "Starting service=%s version=%s debug=%s docs_enabled=%s openai_configured=%s db_ready=%s pruned_sessions=%s",
        APP_NAME,
        PIPELINE_VERSION,
        DEBUG,
        API_DOCS_ENABLED,
        bool(OPENAI_API_KEY and openai_client is not None),
        db_ready(),
        deleted,
    )