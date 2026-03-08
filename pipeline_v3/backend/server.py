from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from main_pipeline import PersonaTamilPipeline
from stage_behaviour_questions import BehaviourQuestionnaire, QUESTIONS


app = FastAPI(title="Persona Tamil App API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for local dev; lock this down later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


behaviour = BehaviourQuestionnaire()
PIPELINE_CACHE: Dict[str, PersonaTamilPipeline] = {}


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


def build_profile_from_answers(user_id: str, answers: Dict[str, Any]) -> Dict[str, Any]:
    behaviour_rules = behaviour._derive_behaviour_rules(answers)
    personality_rag = behaviour._infer_personality_rag_from_answers(answers)

    profile = {
        "profile_version": "app_created",
        "user_id": user_id,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "answers": answers,
        "behaviour_rules": behaviour_rules,
        "rag_personality_hints": personality_rag,
    }
    return behaviour._upgrade_profile(profile)


class ChatRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)


class SaveProfileRequest(BaseModel):
    answers: Dict[str, Any]


class ProfileResponse(BaseModel):
    exists: bool
    profile: Optional[Dict[str, Any]] = None


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/questions")
def get_questions() -> Dict[str, List[Dict[str, Any]]]:
    return {"questions": QUESTIONS}


@app.get("/api/profile/{user_id}", response_model=ProfileResponse)
def get_profile(user_id: str) -> ProfileResponse:
    try:
        if not behaviour.profile_exists(user_id):
            return ProfileResponse(exists=False, profile=None)
        profile = behaviour.load_profile(user_id)
        return ProfileResponse(exists=True, profile=profile)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load profile: {exc}")


@app.post("/api/profile/{user_id}")
def save_profile(user_id: str, payload: SaveProfileRequest) -> Dict[str, Any]:
    try:
        if not user_id.strip():
            raise HTTPException(status_code=400, detail="user_id is required")

        profile = build_profile_from_answers(user_id.strip(), payload.answers or {})
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
        pipeline = get_pipeline(payload.user_id.strip())
        result = pipeline.run(payload.message.strip())
        return {
            "user_id": payload.user_id.strip(),
            "message": payload.message.strip(),
            "result": normalize_pipeline_result(result),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {exc}")