from typing import Any, Dict

from config import TRANSLATION_TEMPERATURE
from stage_openai_core import OpenAICore


class TamilTranslator:
    def __init__(self, core: OpenAICore) -> None:
        self.core = core

    def translate(self, english_text: str, profile: Dict[str, Any]) -> str:
        tone = profile.get("behaviour_rules", {}).get("preferred_tone", "warm and clear")

        system_prompt = (
            "You are an expert English-to-Tamil translator. "
            "Translate into natural, modern, easy-to-read Tamil. "
            "Preserve meaning, tone, and safety. "
            "Do not over-Sanskritize. Do not transliterate English unless necessary."
        )

        user_prompt = f"""
Preferred tone:
{tone}

Translate the following English into natural Tamil.
Keep it culturally clear and easy to understand.
Output only Tamil text.

English text:
{english_text}
""".strip()

        return self.core.generate_text(
            system_prompt,
            user_prompt,
            temperature=TRANSLATION_TEMPERATURE,
            max_output_tokens=1200,
        )