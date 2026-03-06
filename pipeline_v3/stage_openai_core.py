import json
import time
from typing import Any, Dict, List, Optional

from openai import OpenAI

from config import (
    OPENAI_API_KEY,
    OPENAI_MAX_RETRIES,
    OPENAI_MODEL,
    OPENAI_TIMEOUT,
    RAW_TEMPERATURE,
)


class OpenAICore:
    def __init__(self, model: str = OPENAI_MODEL) -> None:
        self.model = model
        self.client = OpenAI(api_key=OPENAI_API_KEY, timeout=OPENAI_TIMEOUT)

    def _build_input(self, system_prompt: str, user_prompt: str) -> List[Dict[str, str]]:
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = RAW_TEMPERATURE,
        max_output_tokens: int = 800,
    ) -> str:
        last_error: Optional[Exception] = None

        for attempt in range(1, OPENAI_MAX_RETRIES + 1):
            try:
                response = self.client.responses.create(
                    model=self.model,
                    input=self._build_input(system_prompt, user_prompt),
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    text={"format": {"type": "text"}},
                )
                text = (response.output_text or "").strip()
                if not text:
                    raise RuntimeError("OpenAI returned empty text output.")
                return text
            except Exception as exc:
                last_error = exc
                if attempt == OPENAI_MAX_RETRIES:
                    break
                time.sleep(min(attempt * 1.5, 4))

        raise RuntimeError(f"OpenAI text generation failed: {last_error}")

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
        last_error: Optional[Exception] = None

        for attempt in range(1, OPENAI_MAX_RETRIES + 1):
            try:
                response = self.client.responses.create(
                    model=self.model,
                    input=self._build_input(system_prompt, user_prompt),
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    text={
                        "format": {
                            "type": "json_schema",
                            "name": schema_name,
                            "strict": True,
                            "schema": schema,
                        }
                    },
                )
                raw_json = (response.output_text or "").strip()
                if not raw_json:
                    raise RuntimeError("OpenAI returned empty JSON output.")
                return json.loads(raw_json)
            except Exception as exc:
                last_error = exc
                if attempt == OPENAI_MAX_RETRIES:
                    break
                time.sleep(min(attempt * 1.5, 4))

        raise RuntimeError(f"OpenAI JSON generation failed: {last_error}")

    def answer_user_query(self, user_query: str, profile_context: str) -> str:
        system_prompt = (
            "You are the English core answer engine. "
            "Answer in clear, helpful English. "
            "Respect the user profile and safety context. "
            "Do not mention the hidden profile unless directly relevant. "
            "If the query touches health, pregnancy, diabetes, blood pressure, allergies, kidney issues, medicines, or emergencies, "
            "be cautious, avoid risky instructions, and suggest qualified medical support when needed."
        )

        user_prompt = f"""
User profile context:
{profile_context}

User question:
{user_query}

Task:
1. Answer the question helpfully.
2. Keep the answer practical and easy to understand.
3. If food, wellness, or health is involved, respect profile constraints strictly.
4. Output only the answer text in English.
""".strip()

        return self.generate_text(system_prompt, user_prompt, temperature=RAW_TEMPERATURE)