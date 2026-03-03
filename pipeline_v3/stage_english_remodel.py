from typing import Dict, Any

from config import REMODEL_TEMPERATURE
from stage_openai_core import OpenAICore


class EnglishRemodeler:
    def __init__(self, core: OpenAICore) -> None:
        self.core = core

    def remodel(self, user_query: str, raw_answer: str, profile: Dict[str, Any]) -> str:
        profile_summary = profile.get("profile_summary", "")
        rules = profile.get("behaviour_rules", {})

        system_prompt = (
            "You are an English remodel engine. "
            "Rewrite the answer so it sounds natural, safe, and personalized. "
            "Keep the meaning faithful. Do not invent facts. "
            "Respect health and food restrictions strictly."
        )

        user_prompt = f"""
User question:
{user_query}

Stored profile summary:
{profile_summary}

Behavior rules:
- Tone: {rules.get('preferred_tone')}
- Length: {rules.get('preferred_answer_length')}
- Avoid items: {', '.join(rules.get('avoid_items', [])) or 'none'}
- Avoid topics: {', '.join(rules.get('avoid_topics', [])) or 'none'}
- Mandatory notes: {' | '.join(rules.get('mandatory_notes', []))}

Raw English answer:
{raw_answer}

Task:
1. Rewrite the answer in polished English.
2. Make it align with the profile.
3. If the query is health-related, keep it cautious and non-dangerous.
4. Do not mention internal rules explicitly unless helpful.
5. Output only final English text.
""".strip()

        return self.core.generate_text(
            system_prompt,
            user_prompt,
            temperature=REMODEL_TEMPERATURE,
            max_output_tokens=1000,
        )