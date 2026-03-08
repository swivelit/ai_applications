from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import OPENAI_API_KEY
from main_pipeline import PersonaTamilPipeline
from stage_behaviour_questions import BehaviourQuestionnaire, QUESTIONS

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


# -----------------------------------------------------------------------------
# App setup
# -----------------------------------------------------------------------------

app = FastAPI(title="Persona Tamil Mobile API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

behaviour = BehaviourQuestionnaire()
PIPELINE_CACHE: Dict[str, PersonaTamilPipeline] = {}

DATA_ROOT = Path(__file__).resolve().parent / "data"
APP_STATE_DIR = DATA_ROOT / "app_state"
APP_STATE_DIR.mkdir(parents=True, exist_ok=True)

openai_client = None
if OPENAI_API_KEY and OpenAI is not None:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)


# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------

class ChatRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)


class SaveProfileRequest(BaseModel):
    answers: Dict[str, Any]


class ProfileResponse(BaseModel):
    exists: bool
    profile: Optional[Dict[str, Any]] = None


class CreateUserRequest(BaseModel):
    name: str
    place: Optional[str] = None
    timezone: str = "Asia/Kolkata"
    assistant_name: str = "Ellie"


class DailyRoutineIn(BaseModel):
    wake_time: str
    sleep_time: str
    work_start: Optional[str] = None
    work_end: Optional[str] = None
    daily_habits: Optional[str] = None


class ParseDatetimeRequest(BaseModel):
    text: str
    timezone: str = "Asia/Kolkata"
    now_iso: Optional[str] = None


class PersonalityAnswersIn(BaseModel):
    answers: Dict[str, Any]


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def get_pipeline(user_id: str) -> PersonaTamilPipeline:
    user_id = (user_id or "").strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    if user_id not in PIPELINE_CACHE:
        PIPELINE_CACHE[user_id] = PersonaTamilPipeline(user_id=user_id)
    return PIPELINE_CACHE[user_id]


def reset_pipeline(user_id: str) -> None:
    if user_id in PIPELINE_CACHE:
        del PIPELINE_CACHE[user_id]


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


def app_state_path(user_id: str) -> Path:
    safe = "".join(ch for ch in (user_id or "").strip() if ch.isalnum() or ch in {"_", "-"})
    if not safe:
        raise HTTPException(status_code=400, detail="Invalid user_id")
    return APP_STATE_DIR / f"{safe}.json"


def load_app_state(user_id: str) -> Dict[str, Any]:
    path = app_state_path(user_id)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "user_id": user_id,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "profile": {
            "name": "",
            "place": "",
            "timezone": "Asia/Kolkata",
            "assistant_name": "Ellie",
        },
        "daily_routine": {
            "wake_time": "07:30",
            "sleep_time": "23:30",
            "work_start": "09:30",
            "work_end": "18:30",
            "daily_habits": "",
        },
    }


def save_app_state(user_id: str, state: Dict[str, Any]) -> None:
    path = app_state_path(user_id)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def normalize_optional(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    v = str(v).strip()
    return v if v else None


def validate_hhmm(v: str) -> None:
    import re
    if not re.match(r"^([01]\d|2[0-3]):([0-5]\d)$", str(v or "").strip()):
        raise HTTPException(status_code=400, detail=f"Invalid time format: {v}")


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
        "user_id": user_id,
        "created_at": datetime.utcnow().isoformat() + "Z",
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
            status_code=500,
            detail="OPENAI_API_KEY is missing or OpenAI client is unavailable.",
        )
    return openai_client


def parse_datetime_with_llm(text: str, timezone: str, now_iso: Optional[str]) -> Dict[str, Any]:
    client = require_openai()
    now_iso = now_iso or datetime.utcnow().isoformat()

    prompt = f"""
You convert natural language time into JSON.

Input:
- timezone: {timezone}
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
        model="gpt-4o-mini",
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
        model="gpt-4o-mini",
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


# -----------------------------------------------------------------------------
# Core health + pipeline endpoints
# -----------------------------------------------------------------------------

@app.get("/")
def root() -> Dict[str, str]:
    return {"status": "ok", "message": "Persona Tamil Mobile API"}

@app.get("/health")
def health_root() -> Dict[str, str]:
    return {"status": "ok"}

@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}

@app.get("/api/questions")
def get_questions() -> Dict[str, List[Dict[str, Any]]]:
    return {"questions": QUESTIONS}

@app.get("/personality/questions")
def get_personality_questions() -> Dict[str, Any]:
    return {"version": 1, "questions": QUESTIONS}

@app.get("/api/profile/{user_id}", response_model=ProfileResponse)
def get_profile(user_id: str) -> ProfileResponse:
    try:
        if not behaviour.profile_exists(user_id):
            ensure_pipeline_profile_exists(user_id)
        profile = behaviour.load_profile(user_id)
        return ProfileResponse(exists=True, profile=profile)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load profile: {exc}")

@app.post("/api/profile/{user_id}")
def save_profile(user_id: str, payload: SaveProfileRequest) -> Dict[str, Any]:
    try:
        if not user_id.strip():
            raise HTTPException(status_code=400, detail="user_id is required")

        state = load_app_state(user_id.strip())
        existing = behaviour.load_profile(user_id.strip()) if behaviour.profile_exists(user_id.strip()) else None
        profile = build_profile_from_answers(
            user_id.strip(),
            payload.answers or {},
            existing_profile=existing,
            app_state=state,
        )
        behaviour.save_profile(user_id.strip(), profile)
        reset_pipeline(user_id.strip())

        return {
            "message": "Profile saved successfully",
            "profile": profile,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save profile: {exc}")

@app.post("/api/profile/{user_id}/reset")
def reset_profile(user_id: str) -> Dict[str, str]:
    try:
        path = behaviour._profile_path(user_id)
        if path.exists():
            path.unlink()
        reset_pipeline(user_id)
        return {"message": "Profile reset successfully"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to reset profile: {exc}")

@app.post("/api/chat")
def chat(payload: ChatRequest) -> Dict[str, Any]:
    try:
        ensure_pipeline_profile_exists(payload.user_id.strip())
        pipeline = get_pipeline(payload.user_id.strip())
        result = pipeline.run(payload.message.strip())
        return {
            "user_id": payload.user_id.strip(),
            "message": payload.message.strip(),
            "result": normalize_pipeline_result(result),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {exc}")


# -----------------------------------------------------------------------------
# Mobile app profile + routine endpoints
# -----------------------------------------------------------------------------

@app.post("/users")
def create_user(payload: CreateUserRequest) -> Dict[str, Any]:
    try:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        state = load_app_state(user_id)
        state["profile"] = {
            "name": payload.name.strip(),
            "place": (payload.place or "").strip(),
            "timezone": payload.timezone.strip() or "Asia/Kolkata",
            "assistant_name": payload.assistant_name.strip() or "Ellie",
        }
        save_app_state(user_id, state)
        ensure_pipeline_profile_exists(user_id)

        return {
            "id": user_id,
            "name": state["profile"]["name"],
            "place": state["profile"]["place"],
            "timezone": state["profile"]["timezone"],
            "assistant_name": state["profile"]["assistant_name"],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create user: {exc}")

@app.get("/users/{user_id}")
def get_user(user_id: str) -> Dict[str, Any]:
    state = load_app_state(user_id)
    profile = state.get("profile", {})
    return {
        "id": user_id,
        "name": profile.get("name", ""),
        "place": profile.get("place", ""),
        "timezone": profile.get("timezone", "Asia/Kolkata"),
        "assistant_name": profile.get("assistant_name", "Ellie"),
    }

@app.get("/users/{user_id}/daily-routine")
def get_daily_routine(user_id: str) -> Dict[str, Any]:
    state = load_app_state(user_id)
    routine = state.get("daily_routine", {})
    return {"user_id": user_id, **routine}

@app.put("/users/{user_id}/daily-routine")
def upsert_daily_routine(user_id: str, payload: DailyRoutineIn) -> Dict[str, Any]:
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
def save_mobile_questionnaire(user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    raw = payload.get("payload", payload)

    mapped = DailyRoutineIn(
        wake_time=str(raw.get("wake") or raw.get("wake_time") or "07:30"),
        sleep_time=str(raw.get("sleep") or raw.get("sleep_time") or "23:30"),
        work_start=raw.get("workStart") or raw.get("work_start"),
        work_end=raw.get("workEnd") or raw.get("work_end"),
        daily_habits=raw.get("dailyHabits") or raw.get("daily_habits"),
    )
    return upsert_daily_routine(user_id, mapped)

@app.get("/users/{user_id}/personality")
def get_personality(user_id: str) -> Dict[str, Any]:
    ensure_pipeline_profile_exists(user_id)
    profile = behaviour.load_profile(user_id)
    return {
        "answers": profile.get("answers", {}),
        "summary": profile.get("profile_summary", ""),
    }

@app.post("/users/{user_id}/personality")
def save_personality_answers(user_id: str, payload: PersonalityAnswersIn) -> Dict[str, Any]:
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
def generate_daily_checkins(user_id: str) -> Dict[str, Any]:
    try:
        return generate_daily_checkins_with_llm(user_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate daily check-ins: {exc}")


# -----------------------------------------------------------------------------
# Datetime parser
# -----------------------------------------------------------------------------

@app.post("/parse-datetime")
def parse_datetime(payload: ParseDatetimeRequest) -> Dict[str, Any]:
    try:
        return parse_datetime_with_llm(payload.text, payload.timezone, payload.now_iso)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to parse datetime: {exc}")


# -----------------------------------------------------------------------------
# Voice -> transcript -> pipeline
# -----------------------------------------------------------------------------

@app.post("/transcribe-and-analyze")
async def transcribe_and_analyze(
    file: UploadFile = File(...),
    user_id: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    client = require_openai()

    suffix = os.path.splitext(file.filename or "")[-1] or ".m4a"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as audio_file:
            transcript_obj = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="ta",
                response_format="json",
            )

        transcript_text = getattr(transcript_obj, "text", "") or ""
        if not transcript_text.strip():
            raise HTTPException(status_code=400, detail="Could not transcribe audio.")

        if not user_id:
            user_id = "guest_user"

        ensure_pipeline_profile_exists(user_id)
        pipeline = get_pipeline(user_id)
        result = pipeline.run(transcript_text.strip())

        return {
            "user_id": user_id,
            "message": transcript_text.strip(),
            "result": normalize_pipeline_result(result),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Voice pipeline failed: {exc}")
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass