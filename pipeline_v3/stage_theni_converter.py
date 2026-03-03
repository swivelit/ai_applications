from typing import Any, Dict

from config import THENI_TEMPERATURE
from stage_openai_core import OpenAICore


class TheniTamilConverter:
    def __init__(self, core: OpenAICore) -> None:
        self.core = core

    def convert(self, tamil_text: str, profile: Dict[str, Any]) -> str:
        tone = profile.get("behaviour_rules", {}).get("preferred_tone", "warm and clear")

        system_prompt = (
            "You convert standard Tamil into colloquial, respectful, easy-to-understand Theni-style Tamil. "
            "Keep the original meaning exactly. "
            "Do not become slang-heavy or rude. "
            "Keep health and safety wording cautious."
        )

        user_prompt = f"""
Preferred tone:
{tone}

Convert the following Tamil into Theni-style Tamil.
Rules:
1. Preserve meaning fully.
2. Keep it readable for common users.
3. Do not add new advice.
4. Output only final Theni Tamil text.

Tamil text:
{tamil_text}
""".strip()

        return self.core.generate_text(
            system_prompt,
            user_prompt,
            temperature=THENI_TEMPERATURE,
            max_output_tokens=1200,
        )