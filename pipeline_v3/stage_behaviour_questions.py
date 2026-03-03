import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from config import (
    MEDICAL_SAFETY_NOTE,
    PREGNANCY_CUSTOM_AVOID_LIST,
    PROFILE_VERSION,
    PROFILES_DIR,
    QUESTION_COUNT,
)


QUESTIONS: List[Dict[str, Any]] = [
    {
        "id": "age_group",
        "prompt": "What is your age group?",
        "type": "single",
        "options": ["18-25", "26-35", "36-45", "46-60", "60+"],
    },
    {
        "id": "gender_context",
        "prompt": "Which option fits you best?",
        "type": "single",
        "options": ["woman", "man", "non-binary", "prefer_not_to_say", "other"],
    },
    {
        "id": "life_stage",
        "prompt": "Which life-stage or health context fits you right now?",
        "type": "single",
        "options": [
            "pregnant",
            "postpartum_or_breastfeeding",
            "trying_to_conceive",
            "none_of_these",
            "prefer_not_to_say",
        ],
    },
    {
        "id": "food_preference",
        "prompt": "What best describes your food preference?",
        "type": "single",
        "options": ["vegetarian", "non_vegetarian", "eggetarian", "vegan", "mixed_flexible"],
    },
    {
        "id": "health_conditions",
        "prompt": "Pick up to 3 health conditions or sensitivities that matter most.",
        "type": "multi",
        "max_choices": 3,
        "options": [
            "none",
            "diabetes_or_sugar_control",
            "blood_pressure_or_heart_care",
            "thyroid_or_hormonal_care",
            "allergy_digestion_kidney_or_other",
        ],
    },
    {
        "id": "food_caution",
        "prompt": "Which food caution best matches you?",
        "type": "single",
        "options": [
            "no_special_caution",
            "avoid_sugary_foods",
            "avoid_spicy_or_oily_foods",
            "avoid_packaged_or_junk_foods",
            "allergy_or_doctor_given_restrictions",
        ],
    },
    {
        "id": "daily_activity",
        "prompt": "How active are you on most days?",
        "type": "single",
        "options": ["mostly_sitting", "light_movement", "moderate_walks", "active_work", "fitness_focused"],
    },
    {
        "id": "sleep_pattern",
        "prompt": "How is your sleep usually?",
        "type": "single",
        "options": ["poor", "inconsistent", "average", "good", "very_good"],
    },
    {
        "id": "personality_style",
        "prompt": "Which personality style sounds most like you?",
        "type": "single",
        "options": ["calm", "friendly", "practical", "ambitious", "emotional_sensitive"],
    },
    {
        "id": "stress_support",
        "prompt": "When stressed, what kind of support helps you most?",
        "type": "single",
        "options": ["gentle_reassurance", "direct_solution", "step_by_step_plan", "motivation", "space_and_time"],
    },
    {
        "id": "communication_tone",
        "prompt": "How should the assistant talk to you?",
        "type": "single",
        "options": ["warm", "respectful", "short_direct", "detailed", "friendly_casual"],
    },
    {
        "id": "answer_length",
        "prompt": "How long should answers usually be?",
        "type": "single",
        "options": ["very_short", "short", "medium", "detailed", "depends_on_question"],
    },
    {
        "id": "hobbies",
        "prompt": "Pick up to 3 things you enjoy most.",
        "type": "multi",
        "max_choices": 3,
        "options": ["music", "movies", "reading", "cooking", "travel"],
    },
    {
        "id": "main_goal",
        "prompt": "What matters most to you right now?",
        "type": "single",
        "options": ["health", "family", "career_or_business", "peace_of_mind", "learning_and_growth"],
    },
    {
        "id": "family_role",
        "prompt": "Which role sounds closest to your current daily life?",
        "type": "single",
        "options": ["student", "working_professional", "homemaker", "caregiver_parent", "self_employed"],
    },
]


class BehaviourQuestionnaire:
    def __init__(self, profiles_dir: Path = PROFILES_DIR) -> None:
        self.profiles_dir = profiles_dir
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    def _profile_path(self, user_id: str) -> Path:
        safe_user_id = "".join(ch for ch in user_id if ch.isalnum() or ch in ("_", "-"))
        if not safe_user_id:
            safe_user_id = "default_user"
        return self.profiles_dir / f"{safe_user_id}.json"

    def profile_exists(self, user_id: str) -> bool:
        return self._profile_path(user_id).exists()

    def load_profile(self, user_id: str) -> Dict[str, Any]:
        path = self._profile_path(user_id)
        if not path.exists():
            raise FileNotFoundError(f"Profile not found for user_id={user_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def save_profile(self, user_id: str, profile: Dict[str, Any]) -> None:
        path = self._profile_path(user_id)
        path.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")

    def ensure_profile(self, user_id: str) -> Dict[str, Any]:
        if self.profile_exists(user_id):
            return self.load_profile(user_id)
        return self.run_first_time_questionnaire(user_id)

    def run_first_time_questionnaire(self, user_id: str) -> Dict[str, Any]:
        print("\nFirst-time profile setup started.")
        print(f"Please answer these {QUESTION_COUNT} questions so responses can be personalized safely.\n")

        answers: Dict[str, Any] = {}

        for index, question in enumerate(QUESTIONS, start=1):
            print(f"Q{index}. {question['prompt']}")
            for option_index, option in enumerate(question["options"], start=1):
                print(f"  {option_index}. {option}")

            if question["type"] == "single":
                answers[question["id"]] = self._ask_single_choice(question)
            else:
                answers[question["id"]] = self._ask_multi_choice(question)
            print()

        behaviour_rules = self._derive_behaviour_rules(answers)
        profile_summary = self._build_profile_summary(answers, behaviour_rules)

        profile = {
            "profile_version": PROFILE_VERSION,
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "answers": answers,
            "behaviour_rules": behaviour_rules,
            "profile_summary": profile_summary,
        }
        self.save_profile(user_id, profile)

        print("Profile created successfully.\n")
        return profile

    def _ask_single_choice(self, question: Dict[str, Any]) -> str:
        max_index = len(question["options"])
        while True:
            raw = input("Select one option number: ").strip()
            if raw.isdigit() and 1 <= int(raw) <= max_index:
                return question["options"][int(raw) - 1]
            print("Invalid choice. Please enter a valid option number.")

    def _ask_multi_choice(self, question: Dict[str, Any]) -> List[str]:
        max_index = len(question["options"])
        max_choices = question.get("max_choices", 3)

        while True:
            raw = input(f"Select up to {max_choices} option numbers separated by comma: ").strip()
            parts = [part.strip() for part in raw.split(",") if part.strip()]
            if not parts:
                print("Please select at least one option.")
                continue
            if not all(part.isdigit() for part in parts):
                print("Only numbers separated by commas are allowed.")
                continue

            indexes = [int(part) for part in parts]
            if any(index < 1 or index > max_index for index in indexes):
                print("One or more options are out of range.")
                continue

            unique_indexes = sorted(set(indexes))
            if len(unique_indexes) > max_choices:
                print(f"Please choose only up to {max_choices} options.")
                continue

            selected = [question["options"][index - 1] for index in unique_indexes]
            if "none" in selected and len(selected) > 1:
                print("If you choose 'none', do not combine it with other options.")
                continue
            return selected

    def _derive_behaviour_rules(self, answers: Dict[str, Any]) -> Dict[str, Any]:
        health_conditions = answers.get("health_conditions", [])
        life_stage = answers.get("life_stage", "")
        food_caution = answers.get("food_caution", "")

        is_pregnant = life_stage == "pregnant"
        has_diabetes = "diabetes_or_sugar_control" in health_conditions
        has_bp = "blood_pressure_or_heart_care" in health_conditions
        has_other_sensitive = "allergy_digestion_kidney_or_other" in health_conditions

        avoid_items: List[str] = []
        avoid_topics: List[str] = []
        mandatory_notes: List[str] = [MEDICAL_SAFETY_NOTE]

        if is_pregnant:
            avoid_items.extend(PREGNANCY_CUSTOM_AVOID_LIST)
            mandatory_notes.append(
                "Business rule: when the user is pregnant, do not recommend pineapple or any risky food/medicine suggestion."
            )

        if has_diabetes or food_caution == "avoid_sugary_foods":
            avoid_items.extend(["high sugar drinks", "excess sweets", "dessert-heavy suggestions"])
            mandatory_notes.append("For sugar-control users, avoid casual advice that increases sugar load.")

        if has_bp:
            avoid_items.extend(["high salt foods", "energy drinks", "stimulant-heavy suggestions"])
            mandatory_notes.append("For blood pressure or heart-care users, avoid high-salt and stimulant-heavy advice.")

        if has_other_sensitive or food_caution == "allergy_or_doctor_given_restrictions":
            avoid_topics.append("confident medical certainty")
            mandatory_notes.append(
                "For allergy, digestion, kidney, or doctor-restricted users, avoid ingredient-specific certainty unless the user confirms safety."
            )

        tone_map = {
            "warm": "warm, caring, and clear",
            "respectful": "respectful and polished",
            "short_direct": "brief and direct",
            "detailed": "detailed and structured",
            "friendly_casual": "friendly and conversational",
        }

        answer_length_map = {
            "very_short": "2-3 lines",
            "short": "1 short paragraph",
            "medium": "1-2 balanced paragraphs",
            "detailed": "2-4 detailed paragraphs or bullet points",
            "depends_on_question": "adapt length to question complexity",
        }

        return {
            "preferred_tone": tone_map.get(answers.get("communication_tone", "warm"), "warm and clear"),
            "preferred_answer_length": answer_length_map.get(answers.get("answer_length", "medium"), "1-2 paragraphs"),
            "primary_goal": answers.get("main_goal"),
            "avoid_items": sorted(set(avoid_items)),
            "avoid_topics": sorted(set(avoid_topics)),
            "mandatory_notes": mandatory_notes,
            "health_flags": {
                "pregnant": is_pregnant,
                "diabetes_or_sugar_control": has_diabetes,
                "blood_pressure_or_heart_care": has_bp,
                "allergy_digestion_kidney_or_other": has_other_sensitive,
            },
        }

    def _build_profile_summary(self, answers: Dict[str, Any], behaviour_rules: Dict[str, Any]) -> str:
        hobbies = ", ".join(answers.get("hobbies", [])) or "no hobby preference recorded"
        health_conditions = ", ".join(answers.get("health_conditions", [])) or "none"
        avoid_items = ", ".join(behaviour_rules.get("avoid_items", [])) or "none"

        return (
            f"The user belongs to the {answers.get('age_group')} age group and identifies their context as "
            f"{answers.get('gender_context')}. Their current life-stage is {answers.get('life_stage')}. "
            f"They prefer a {answers.get('food_preference')} food style, with health-related context recorded as: {health_conditions}. "
            f"Important food caution: {answers.get('food_caution')}. Their daily activity is {answers.get('daily_activity')} and sleep is usually {answers.get('sleep_pattern')}. "
            f"Their personality comes across as {answers.get('personality_style')}, and during stress they prefer {answers.get('stress_support')}. "
            f"The assistant should use a {behaviour_rules.get('preferred_tone')} tone and usually keep answers to {behaviour_rules.get('preferred_answer_length')}. "
            f"They enjoy {hobbies}, and their current priority is {answers.get('main_goal')}. "
            f"Their daily role is closest to {answers.get('family_role')}. Avoid recommending: {avoid_items}."
        )

    def build_runtime_context(self, profile: Dict[str, Any]) -> str:
        rules = profile.get("behaviour_rules", {})
        notes = "\n- ".join(rules.get("mandatory_notes", []))
        avoid_items = ", ".join(rules.get("avoid_items", [])) or "none"
        avoid_topics = ", ".join(rules.get("avoid_topics", [])) or "none"

        return f"""
Stored user profile summary:
{profile.get('profile_summary', '')}

Behavior rules:
- Preferred tone: {rules.get('preferred_tone', 'warm and clear')}
- Preferred answer length: {rules.get('preferred_answer_length', '1-2 paragraphs')}
- Avoid items: {avoid_items}
- Avoid topics: {avoid_topics}
- Mandatory notes:
- {notes if notes else 'No special notes'}
""".strip()