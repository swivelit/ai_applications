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
    OPENAI_API_KEY,
    OPENAI_BACKOFF_BASE_SECONDS,
    OPENAI_CACHE_SIZE,
    OPENAI_MAX_RETRIES,
    OPENAI_MODEL,
    OPENAI_TIMEOUT,
    RAW_TEMPERATURE,
)


class OpenAICore:
    """Thin OpenAI wrapper with caching, retries, and structured helpers."""

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
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
            stripped = re.sub(r"\s*```$", "", stripped)
        return stripped.strip()

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
                if response_format is None:
                    payload["text"] = {"format": {"type": "text"}}
                else:
                    payload["text"] = {"format": response_format}

                response = self.client.responses.create(**payload)
                text = (response.output_text or "").strip()
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

    def generate_text_with_reason(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = RAW_TEMPERATURE,
        max_output_tokens: int = 800,
    ) -> Tuple[str, str]:
        schema = {
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
                "style_reason": {"type": "string"},
            },
            "required": ["answer", "style_reason"],
            "additionalProperties": False,
        }
        data = self.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema_name="text_with_reason",
            schema=schema,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        return str(data.get("answer", "")).strip(), str(data.get("style_reason", "")).strip()

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