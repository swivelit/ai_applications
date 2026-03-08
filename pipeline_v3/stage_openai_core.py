from __future__ import annotations

import hashlib
import json
import random
import re
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI

from config import (
    ENABLE_ANSWER_REVIEW,
    OPENAI_API_KEY,
    OPENAI_BACKOFF_BASE_SECONDS,
    OPENAI_CACHE_SIZE,
    OPENAI_MAX_RETRIES,
    OPENAI_MODEL,
    OPENAI_TIMEOUT,
    RAW_TEMPERATURE,
)


class OpenAICore:
    """Thin OpenAI wrapper with caching, retries, structured helpers, and answer review."""

    def __init__(self, model: str = OPENAI_MODEL) -> None:
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is missing. Add it to .env before running the pipeline.")

        self.model = model
        self.client = OpenAI(api_key=OPENAI_API_KEY, timeout=OPENAI_TIMEOUT)
        self._cache: "OrderedDict[str, str]" = OrderedDict()

    @staticmethod
    def _build_input(system_prompt: str, user_prompt: str) -> List[Dict[str, str]]:
        return [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_prompt.strip()},
        ]

    def _cache_key(
        self,
        *,
        mode: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_output_tokens: int,
        schema_name: str = "",
        schema: Optional[Dict[str, Any]] = None,
    ) -> str:
        payload = {
            "mode": mode,
            "model": self.model,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
            "schema_name": schema_name,
            "schema": schema or {},
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    def _cache_get(self, key: str) -> Optional[str]:
        value = self._cache.get(key)
        if value is None:
            return None
        self._cache.move_to_end(key)
        return value

    def _cache_set(self, key: str, value: str) -> None:
        self._cache[key] = value
        self._cache.move_to_end(key)
        while len(self._cache) > OPENAI_CACHE_SIZE:
            self._cache.popitem(last=False)

    @staticmethod
    def _strip_json_fences(text: str) -> str:
        stripped = str(text or "").strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
            stripped = re.sub(r"\s*```$", "", stripped)
        return stripped.strip()

    @staticmethod
    def _extract_response_text(response: Any) -> str:
        text = getattr(response, "output_text", None)
        if text:
            return str(text).strip()

        output = getattr(response, "output", None) or []
        collected: List[str] = []
        for item in output:
            content = getattr(item, "content", None) or []
            for part in content:
                part_text = getattr(part, "text", None)
                if part_text:
                    collected.append(str(part_text))
                elif isinstance(part, dict) and part.get("text"):
                    collected.append(str(part["text"]))
        return "\n".join(chunk.strip() for chunk in collected if str(chunk).strip()).strip()

    def _request_text(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float,
        max_output_tokens: int,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> str:
        last_error: Optional[Exception] = None

        for attempt in range(1, OPENAI_MAX_RETRIES + 1):
            try:
                payload: Dict[str, Any] = {
                    "model": self.model,
                    "input": self._build_input(system_prompt, user_prompt),
                    "temperature": temperature,
                    "max_output_tokens": max_output_tokens,
                }
                payload["text"] = {"format": response_format or {"type": "text"}}

                response = self.client.responses.create(**payload)
                text = self._extract_response_text(response)
                if not text:
                    raise RuntimeError("OpenAI returned empty output.")
                return text
            except Exception as exc:
                last_error = exc
                if attempt == OPENAI_MAX_RETRIES:
                    break
                sleep_seconds = min(
                    OPENAI_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)) + random.uniform(0.0, 0.3),
                    8.0,
                )
                time.sleep(sleep_seconds)

        raise RuntimeError(f"OpenAI request failed after {OPENAI_MAX_RETRIES} attempt(s): {last_error}")

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = RAW_TEMPERATURE,
        max_output_tokens: int = 800,
    ) -> str:
        cache_key = self._cache_key(
            mode="text",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        text = self._request_text(
            system_prompt,
            user_prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            response_format=None,
        )
        self._cache_set(cache_key, text)
        return text

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
        schema: Dict[str, Any],
        *,
        temperature: float = 0.2,
        max_output_tokens: int = 1200,
    ) -> Dict[str, Any]:
        cache_key = self._cache_key(
            mode="json",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            schema_name=schema_name,
            schema=schema,
        )
        cached = self._cache_get(cache_key)
        if cached is not None:
            return json.loads(cached)

        raw_json = self._request_text(
            system_prompt,
            user_prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            response_format={
                "type": "json_schema",
                "name": schema_name,
                "strict": True,
                "schema": schema,
            },
        )
        cleaned = self._strip_json_fences(raw_json)
        parsed = json.loads(cleaned)
        serialized = json.dumps(parsed, ensure_ascii=False, sort_keys=True)
        self._cache_set(cache_key, serialized)
        return parsed

    def answer_user_query_structured(self, user_query: str, profile_context: str) -> Dict[str, str]:
        system_prompt = (
            "You are the English core answer engine for a persona-aware assistant. "
            "Answer in clear, practical English. Respect the user profile and safety context. "
            "Do not mention hidden profiling. If the query touches health, pregnancy, diabetes, blood pressure, "
            "allergies, kidney issues, medicines, or emergencies, stay cautious, avoid risky instructions, and "
            "suggest qualified medical support when needed."
        )
        schema = {
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
                "answer_style": {"type": "string"},
                "risk_level": {"type": "string", "enum": ["low", "medium", "high"]},
                "safety_notes": {"type": "string"},
            },
            "required": ["answer", "answer_style", "risk_level", "safety_notes"],
            "additionalProperties": False,
        }

        user_prompt = f"""
User profile context:
{profile_context}

User question:
{user_query}

Task:
1. Answer the user's question helpfully.
2. Prefer practical and easy-to-understand wording.
3. Respect any caution, avoidance, or personalization constraints in the profile.
4. Avoid invented facts.
5. Keep the answer faithful, realistic, and safe.
6. Output JSON following the schema.
""".strip()

        data = self.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema_name="core_answer_result",
            schema=schema,
            temperature=RAW_TEMPERATURE,
            max_output_tokens=1000,
        )
        answer = str(data.get("answer", "")).strip()
        if not answer:
            answer = self.answer_user_query(user_query, profile_context)
        return {
            "answer": answer,
            "answer_style": str(data.get("answer_style", "practical")).strip() or "practical",
            "risk_level": str(data.get("risk_level", "low")).strip() or "low",
            "safety_notes": str(data.get("safety_notes", "")).strip(),
        }

    def answer_user_query(self, user_query: str, profile_context: str) -> str:
        system_prompt = (
            "You are the English core answer engine for a persona-aware assistant. "
            "Answer in clear, practical English. Respect the user profile and safety context. "
            "Do not mention hidden profiling. If the query touches health, pregnancy, diabetes, blood pressure, "
            "allergies, kidney issues, medicines, or emergencies, stay cautious, avoid risky instructions, and "
            "suggest qualified medical support when needed."
        )

        user_prompt = f"""
User profile context:
{profile_context}

User question:
{user_query}

Task:
1. Answer the user's question helpfully.
2. Prefer practical and easy-to-understand wording.
3. Respect any caution, avoidance, or personalization constraints in the profile.
4. Avoid invented facts.
5. Output only the answer text in English.
""".strip()

        return self.generate_text(system_prompt, user_prompt, temperature=RAW_TEMPERATURE)

    def review_answer(self, user_query: str, answer: str, profile_context: str) -> Dict[str, str]:
        if not ENABLE_ANSWER_REVIEW:
            return {
                "final_answer": answer,
                "keep_original": "true",
                "review_note": "review disabled",
            }

        schema = {
            "type": "object",
            "properties": {
                "final_answer": {"type": "string"},
                "keep_original": {"type": "string", "enum": ["true", "false"]},
                "review_note": {"type": "string"},
            },
            "required": ["final_answer", "keep_original", "review_note"],
            "additionalProperties": False,
        }
        system_prompt = (
            "You are a strict answer reviewer. Improve the answer only if it becomes safer, clearer, "
            "or more faithful to the user context. Do not add new facts. Keep the answer concise."
        )
        user_prompt = f"""
User profile context:
{profile_context}

User question:
{user_query}

Candidate answer:
{answer}

Task:
- Keep the answer if it is already good.
- Revise only when needed for clarity, tone, or safety.
- Do not invent facts.
- Output JSON following the schema.
""".strip()
        data = self.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema_name="answer_review",
            schema=schema,
            temperature=0.15,
            max_output_tokens=900,
        )
        final_answer = str(data.get("final_answer", "")).strip() or answer
        keep_original = str(data.get("keep_original", "true")).strip().lower()
        if keep_original == "true":
            final_answer = answer
        return {
            "final_answer": final_answer,
            "keep_original": keep_original,
            "review_note": str(data.get("review_note", "")).strip(),
        }