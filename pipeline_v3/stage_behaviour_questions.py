from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config import (
    BASE_DIR,
    DATA_DIR,
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


# ---------------------------------------------------------------------
# Advanced local RAG utilities
# ---------------------------------------------------------------------


class LocalHybridRAG:
    """
    Lightweight local hybrid retrieval:
    - Unicode-safe normalization
    - query expansion
    - TF-IDF cosine-like similarity
    - lexical overlap
    - MMR diversity reranking
    """

    def __init__(self, documents: List[Dict[str, Any]]) -> None:
        self.documents = documents or []
        self._fitted = False
        self.vocab: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.doc_vectors: List[Dict[str, float]] = []
        self.doc_tokens: List[List[str]] = []
        self.stopwords = {
            "a", "an", "the", "and", "or", "but", "if", "to", "for", "of", "in", "on",
            "at", "by", "with", "from", "as", "is", "are", "was", "were", "be", "been",
            "this", "that", "these", "those", "it", "its", "into", "about", "your",
            "you", "user", "question", "answer", "profile", "assistant", "most", "best",
            "usually", "right", "now", "how", "what", "which", "when", "do", "does",
            "can", "should", "would", "could", "up", "one", "two", "three"
        }
        self.synonyms = {
            "pregnancy": ["pregnant", "conceive", "breastfeeding", "postpartum"],
            "sugar": ["diabetes", "sweet", "dessert", "glucose"],
            "blood": ["pressure", "heart", "salt"],
            "tone": ["style", "communication", "talk"],
            "stress": ["support", "anxiety", "reassurance"],
            "health": ["wellness", "medical", "condition", "safe", "safety"],
            "food": ["diet", "meal", "eat", "eating", "preference", "caution"],
            "personality": ["trait", "temperament", "behavior", "behaviour"],
            "work": ["career", "professional", "business", "job"],
            "family": ["parent", "caregiver", "home", "homemaker"],
        }
        self._fit()

    @staticmethod
    def _normalize(text: Any) -> str:
        text = "" if text is None else str(text)
        text = unicodedata.normalize("NFKC", text).lower().strip()
        text = text.replace("_", " ").replace("-", " ")
        text = re.sub(r"[^\w\s\u0B80-\u0BFF]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _tokenize(self, text: Any) -> List[str]:
        normalized = self._normalize(text)
        tokens = [t for t in normalized.split() if t and t not in self.stopwords]
        return tokens

    def _expand_tokens(self, tokens: List[str]) -> List[str]:
        expanded = list(tokens)
        token_set = set(tokens)

        for token in list(token_set):
            if token in self.synonyms:
                expanded.extend(self.synonyms[token])

        # reverse synonym lookup
        for key, values in self.synonyms.items():
            if token_set.intersection(values):
                expanded.append(key)
                expanded.extend(values)

        return expanded

    def _fit(self) -> None:
        if not self.documents:
            self._fitted = True
            return

        all_doc_tokens: List[List[str]] = []
        df_counter: Counter = Counter()

        for doc in self.documents:
            text = self._normalize(doc.get("text", ""))
            tokens = self._tokenize(text)
            self.doc_tokens.append(tokens)
            all_doc_tokens.append(tokens)
            for token in set(tokens):
                df_counter[token] += 1

        self.vocab = {token: idx for idx, token in enumerate(sorted(df_counter.keys()))}
        total_docs = max(len(self.documents), 1)

        self.idf = {
            token: math.log((1 + total_docs) / (1 + df_counter[token])) + 1.0
            for token in df_counter
        }

        self.doc_vectors = [self._tfidf_vector(tokens) for tokens in all_doc_tokens]
        self._fitted = True

    def _tfidf_vector(self, tokens: List[str]) -> Dict[str, float]:
        if not tokens:
            return {}

        counts = Counter(tokens)
        total = sum(counts.values()) or 1
        vector: Dict[str, float] = {}

        for token, count in counts.items():
            tf = count / total
            vector[token] = tf * self.idf.get(token, 1.0)

        norm = math.sqrt(sum(value * value for value in vector.values())) or 1.0
        return {token: value / norm for token, value in vector.items()}

    @staticmethod
    def _cosine_sparse(v1: Dict[str, float], v2: Dict[str, float]) -> float:
        if not v1 or not v2:
            return 0.0
        if len(v1) > len(v2):
            v1, v2 = v2, v1
        return sum(value * v2.get(token, 0.0) for token, value in v1.items())

    @staticmethod
    def _jaccard(tokens1: List[str], tokens2: List[str]) -> float:
        s1, s2 = set(tokens1), set(tokens2)
        if not s1 or not s2:
            return 0.0
        return len(s1 & s2) / max(len(s1 | s2), 1)

    def _score(self, query: str, doc_idx: int) -> float:
        query_tokens = self._expand_tokens(self._tokenize(query))
        query_vec = self._tfidf_vector(query_tokens)

        semantic = self._cosine_sparse(query_vec, self.doc_vectors[doc_idx])
        lexical = self._jaccard(query_tokens, self.doc_tokens[doc_idx])

        # small metadata boost
        doc = self.documents[doc_idx]
        meta_text = " ".join(str(v) for v in doc.get("metadata", {}).values())
        meta_tokens = self._tokenize(meta_text)
        meta_overlap = self._jaccard(query_tokens, meta_tokens)

        return (0.68 * semantic) + (0.24 * lexical) + (0.08 * meta_overlap)

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        mmr_lambda: float = 0.75,
        min_score: float = 0.03,
    ) -> List[Dict[str, Any]]:
        if not self._fitted or not self.documents:
            return []

        scored: List[Tuple[int, float]] = []
        for idx in range(len(self.documents)):
            score = self._score(query, idx)
            if score >= min_score:
                scored.append((idx, score))

        if not scored:
            return []

        scored.sort(key=lambda x: x[1], reverse=True)
        candidate_indices = [idx for idx, _ in scored[: max(top_k * 3, top_k)]]

        selected: List[int] = []
        selected_results: List[Dict[str, Any]] = []

        while candidate_indices and len(selected) < top_k:
            best_idx = None
            best_mmr = -1e9

            for idx in list(candidate_indices):
                relevance = next(score for cand_idx, score in scored if cand_idx == idx)

                diversity_penalty = 0.0
                if selected:
                    similarity_to_selected = max(
                        self._cosine_sparse(self.doc_vectors[idx], self.doc_vectors[s_idx])
                        for s_idx in selected
                    )
                    diversity_penalty = similarity_to_selected

                mmr_score = (mmr_lambda * relevance) - ((1 - mmr_lambda) * diversity_penalty)

                if mmr_score > best_mmr:
                    best_mmr = mmr_score
                    best_idx = idx

            if best_idx is None:
                break

            selected.append(best_idx)
            candidate_indices.remove(best_idx)

            original_score = next(score for cand_idx, score in scored if cand_idx == best_idx)
            result = dict(self.documents[best_idx])
            result["retrieval_score"] = round(float(original_score), 4)
            selected_results.append(result)

        return selected_results


# ---------------------------------------------------------------------
# Behaviour questionnaire + RAG
# ---------------------------------------------------------------------


class BehaviourQuestionnaire:
    def __init__(self, profiles_dir: Path = PROFILES_DIR) -> None:
        self.profiles_dir = profiles_dir
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

        self.personality_dataset_path = DATA_DIR / "personality_15_question_dataset.json"
        self.rag = LocalHybridRAG(self._build_knowledge_documents())

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
        personality_rag = self._infer_personality_rag_from_answers(answers)
        profile_summary = self._build_profile_summary(answers, behaviour_rules, personality_rag)

        profile = {
            "profile_version": PROFILE_VERSION,
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "answers": answers,
            "behaviour_rules": behaviour_rules,
            "profile_summary": profile_summary,
            "rag_personality_hints": personality_rag,
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

        personality_style = answers.get("personality_style", "")
        stress_support = answers.get("stress_support", "")
        main_goal = answers.get("main_goal", "")
        family_role = answers.get("family_role", "")

        response_style_bias: List[str] = []
        if personality_style == "calm":
            response_style_bias.append("Keep wording calm and steady.")
        elif personality_style == "friendly":
            response_style_bias.append("Use encouraging and socially warm language.")
        elif personality_style == "practical":
            response_style_bias.append("Prefer concrete, actionable steps over abstract advice.")
        elif personality_style == "ambitious":
            response_style_bias.append("Frame suggestions in goal-oriented language.")
        elif personality_style == "emotional_sensitive":
            response_style_bias.append("Use gentle, emotionally careful wording.")

        if stress_support == "gentle_reassurance":
            response_style_bias.append("Start with reassurance before giving advice.")
        elif stress_support == "direct_solution":
            response_style_bias.append("Give the answer quickly, then supporting detail.")
        elif stress_support == "step_by_step_plan":
            response_style_bias.append("Prefer numbered or stepwise explanations.")
        elif stress_support == "motivation":
            response_style_bias.append("Use a supportive motivational tone without exaggeration.")
        elif stress_support == "space_and_time":
            response_style_bias.append("Avoid sounding pushy or urgent unless safety requires it.")

        if main_goal == "health":
            response_style_bias.append("Prioritize health-conscious framing.")
        elif main_goal == "family":
            response_style_bias.append("Acknowledge family practicality when relevant.")
        elif main_goal == "career_or_business":
            response_style_bias.append("Prefer efficiency and clarity.")
        elif main_goal == "peace_of_mind":
            response_style_bias.append("Reduce unnecessary alarm in phrasing.")
        elif main_goal == "learning_and_growth":
            response_style_bias.append("Include brief explanatory context when helpful.")

        if family_role == "student":
            response_style_bias.append("Use simple, approachable language.")
        elif family_role == "working_professional":
            response_style_bias.append("Keep answers time-efficient and practical.")
        elif family_role == "homemaker":
            response_style_bias.append("Allow home and routine-oriented framing where relevant.")
        elif family_role == "caregiver_parent":
            response_style_bias.append("Be mindful of time, stress, and caregiving load.")
        elif family_role == "self_employed":
            response_style_bias.append("Keep recommendations flexible and outcome-focused.")

        return {
            "preferred_tone": tone_map.get(answers.get("communication_tone", "warm"), "warm and clear"),
            "preferred_answer_length": answer_length_map.get(answers.get("answer_length", "medium"), "1-2 paragraphs"),
            "primary_goal": answers.get("main_goal"),
            "avoid_items": sorted(set(avoid_items)),
            "avoid_topics": sorted(set(avoid_topics)),
            "mandatory_notes": mandatory_notes,
            "response_style_bias": response_style_bias,
            "health_flags": {
                "pregnant": is_pregnant,
                "diabetes_or_sugar_control": has_diabetes,
                "blood_pressure_or_heart_care": has_bp,
                "allergy_digestion_kidney_or_other": has_other_sensitive,
            },
        }

    def _build_profile_summary(
        self,
        answers: Dict[str, Any],
        behaviour_rules: Dict[str, Any],
        personality_rag: Optional[Dict[str, Any]] = None,
    ) -> str:
        hobbies = ", ".join(answers.get("hobbies", [])) or "no hobby preference recorded"
        health_conditions = ", ".join(answers.get("health_conditions", [])) or "none"
        avoid_items = ", ".join(behaviour_rules.get("avoid_items", [])) or "none"

        personality_line = ""
        if personality_rag:
            top_traits = ", ".join(personality_rag.get("top_traits", [])) or "balanced"
            personality_hint = personality_rag.get("personality_summary", "")
            personality_line = (
                f" Retrieved personality hints suggest traits such as {top_traits}. "
                f"{personality_hint}"
            )

        return (
            f"The user belongs to the {answers.get('age_group')} age group and identifies their context as "
            f"{answers.get('gender_context')}. Their current life-stage is {answers.get('life_stage')}. "
            f"They prefer a {answers.get('food_preference')} food style, with health-related context recorded as: {health_conditions}. "
            f"Important food caution: {answers.get('food_caution')}. Their daily activity is {answers.get('daily_activity')} and sleep is usually {answers.get('sleep_pattern')}. "
            f"Their personality comes across as {answers.get('personality_style')}, and during stress they prefer {answers.get('stress_support')}. "
            f"The assistant should use a {behaviour_rules.get('preferred_tone')} tone and usually keep answers to {behaviour_rules.get('preferred_answer_length')}. "
            f"They enjoy {hobbies}, and their current priority is {answers.get('main_goal')}. "
            f"Their daily role is closest to {answers.get('family_role')}. Avoid recommending: {avoid_items}."
            f"{personality_line}"
        )

    def _build_knowledge_documents(self) -> List[Dict[str, Any]]:
        docs: List[Dict[str, Any]] = []

        for q in QUESTIONS:
            option_text = ", ".join(q.get("options", []))
            docs.append(
                {
                    "doc_id": f"question::{q['id']}",
                    "text": (
                        f"Question id {q['id']}. Prompt: {q['prompt']}. "
                        f"Type: {q['type']}. Options: {option_text}."
                    ),
                    "metadata": {
                        "kind": "question",
                        "question_id": q["id"],
                        "type": q["type"],
                    },
                }
            )

            if q["id"] == "life_stage":
                docs.append(
                    {
                        "doc_id": "rule::pregnancy",
                        "text": (
                            "If life stage is pregnant or related to conception or breastfeeding, "
                            "recommend cautious, medically safe, non-risky guidance. Avoid pineapple, alcohol, smoking, "
                            "tobacco, unprescribed medicine, and crash dieting. Encourage clinician support for diagnosis and medication questions."
                        ),
                        "metadata": {"kind": "rule", "topic": "pregnancy"},
                    }
                )

            if q["id"] == "health_conditions":
                docs.append(
                    {
                        "doc_id": "rule::diabetes_bp_allergy",
                        "text": (
                            "For diabetes or sugar control, avoid high sugar drinks and dessert-heavy suggestions. "
                            "For blood pressure or heart care, avoid high salt foods, energy drinks, and stimulant-heavy advice. "
                            "For allergy, digestion, kidney, or doctor restrictions, avoid confident ingredient-specific certainty."
                        ),
                        "metadata": {"kind": "rule", "topic": "health_conditions"},
                    }
                )

            if q["id"] == "communication_tone":
                docs.append(
                    {
                        "doc_id": "rule::tone",
                        "text": (
                            "Assistant tone should match user preference: warm, respectful, short direct, detailed, or friendly casual."
                        ),
                        "metadata": {"kind": "rule", "topic": "tone"},
                    }
                )

            if q["id"] == "answer_length":
                docs.append(
                    {
                        "doc_id": "rule::answer_length",
                        "text": (
                            "Answer length can be very short, short, medium, detailed, or adaptive depending on question complexity."
                        ),
                        "metadata": {"kind": "rule", "topic": "answer_length"},
                    }
                )

        # personality benchmark dataset
        if self.personality_dataset_path.exists():
            try:
                personality_data = json.loads(self.personality_dataset_path.read_text(encoding="utf-8"))
                for item in personality_data.get("questions", []):
                    qid = item.get("id")
                    qtext = item.get("question", "")
                    for opt_index, option in enumerate(item.get("options", []), start=1):
                        answer = option.get("answer", "")
                        trait = option.get("trait", "unknown")
                        docs.append(
                            {
                                "doc_id": f"personality::{qid}::{opt_index}",
                                "text": (
                                    f"Personality benchmark question: {qtext}. "
                                    f"Possible answer: {answer}. Associated trait: {trait}."
                                ),
                                "metadata": {
                                    "kind": "personality_example",
                                    "trait": trait,
                                    "source_question_id": qid,
                                },
                            }
                        )

                sample_output = personality_data.get("sample_output", {})
                trait_scores = sample_output.get("trait_scores", {})
                docs.append(
                    {
                        "doc_id": "personality::summary",
                        "text": (
                            f"Sample personality summary: {sample_output.get('personality_summary', '')}. "
                            f"Trait scores example: {json.dumps(trait_scores, ensure_ascii=False)}."
                        ),
                        "metadata": {
                            "kind": "personality_summary",
                            "source": "personality_15_question_dataset",
                        },
                    }
                )
            except Exception:
                pass

        return docs

    def _infer_personality_rag_from_answers(self, answers: Dict[str, Any]) -> Dict[str, Any]:
        """
        Maps the stored answers into a weak personality-trait estimate,
        then enriches it with retrieved benchmark examples.
        """
        trait_scores: Counter = Counter()

        hobby_map = {
            "reading": "introverted",
            "movies": "calm_under_stress",
            "music": "social",
            "cooking": "disciplined",
            "travel": "risk_taker",
        }
        tone_map = {
            "warm": "social",
            "respectful": "disciplined",
            "short_direct": "disciplined",
            "detailed": "health_focused",
            "friendly_casual": "extroverted",
        }
        personality_map = {
            "calm": "calm_under_stress",
            "friendly": "social",
            "practical": "disciplined",
            "ambitious": "active",
            "emotional_sensitive": "introverted",
        }
        activity_map = {
            "mostly_sitting": "introverted",
            "light_movement": "health_focused",
            "moderate_walks": "health_focused",
            "active_work": "active",
            "fitness_focused": "active",
        }

        for hobby in answers.get("hobbies", []):
            mapped = hobby_map.get(hobby)
            if mapped:
                trait_scores[mapped] += 1

        for field_name, mapping in [
            ("communication_tone", tone_map),
            ("personality_style", personality_map),
            ("daily_activity", activity_map),
        ]:
            value = answers.get(field_name)
            mapped = mapping.get(value)
            if mapped:
                trait_scores[mapped] += 2

        if answers.get("main_goal") == "health":
            trait_scores["health_focused"] += 2
        if answers.get("stress_support") == "step_by_step_plan":
            trait_scores["disciplined"] += 2
        if answers.get("stress_support") == "space_and_time":
            trait_scores["introverted"] += 1
        if answers.get("stress_support") == "motivation":
            trait_scores["extroverted"] += 1

        top_traits = [trait for trait, _ in trait_scores.most_common(3)]

        retrieval_query = " ".join(
            [
                str(answers.get("personality_style", "")),
                str(answers.get("communication_tone", "")),
                str(answers.get("stress_support", "")),
                str(answers.get("daily_activity", "")),
                str(answers.get("main_goal", "")),
                " ".join(answers.get("hobbies", [])),
                " ".join(top_traits),
            ]
        ).strip()

        retrieved = self.rag.retrieve(retrieval_query, top_k=4, min_score=0.02)
        retrieved_traits = []
        for item in retrieved:
            trait = item.get("metadata", {}).get("trait")
            if trait:
                retrieved_traits.append(trait)

        merged_traits = list(dict.fromkeys(top_traits + retrieved_traits))[:4]
        personality_summary = ""
        if merged_traits:
            personality_summary = (
                "Based on the questionnaire and retrieved personality examples, "
                f"the user appears relatively {', '.join(merged_traits)}."
            )

        return {
            "top_traits": merged_traits,
            "retrieved_examples": [
                {
                    "doc_id": item.get("doc_id"),
                    "text": item.get("text", ""),
                    "score": item.get("retrieval_score", 0.0),
                }
                for item in retrieved
            ],
            "personality_summary": personality_summary,
        }

    def _profile_to_query(self, profile: Dict[str, Any], user_query: Optional[str] = None) -> str:
        answers = profile.get("answers", {})
        rules = profile.get("behaviour_rules", {})
        parts = [
            str(user_query or ""),
            str(answers.get("life_stage", "")),
            str(answers.get("food_preference", "")),
            " ".join(answers.get("health_conditions", [])),
            str(answers.get("food_caution", "")),
            str(answers.get("communication_tone", "")),
            str(answers.get("answer_length", "")),
            str(answers.get("personality_style", "")),
            str(answers.get("stress_support", "")),
            str(answers.get("main_goal", "")),
            str(answers.get("family_role", "")),
            " ".join(answers.get("hobbies", [])),
            " ".join(rules.get("avoid_items", [])),
            " ".join(rules.get("avoid_topics", [])),
        ]
        return " ".join(part for part in parts if part).strip()

    def build_runtime_context(self, profile: Dict[str, Any], user_query: Optional[str] = None) -> str:
        rules = profile.get("behaviour_rules", {})
        notes = "\n- ".join(rules.get("mandatory_notes", []))
        avoid_items = ", ".join(rules.get("avoid_items", [])) or "none"
        avoid_topics = ", ".join(rules.get("avoid_topics", [])) or "none"
        style_bias = "\n- ".join(rules.get("response_style_bias", [])) or "No style bias available"

        retrieval_query = self._profile_to_query(profile, user_query=user_query)
        retrieved = self.rag.retrieve(retrieval_query, top_k=6, min_score=0.02)

        retrieved_context_lines: List[str] = []
        for item in retrieved:
            meta = item.get("metadata", {})
            kind = meta.get("kind", "unknown")
            retrieved_context_lines.append(
                f"- [{kind}] {item.get('text', '')} (score={item.get('retrieval_score', 0.0)})"
            )

        rag_hints = profile.get("rag_personality_hints", {})
        rag_traits = ", ".join(rag_hints.get("top_traits", [])) or "none"
        rag_summary = rag_hints.get("personality_summary", "No additional personality summary available.")

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

Response style bias:
- {style_bias}

Retrieved personality hints:
- Top traits: {rag_traits}
- Summary: {rag_summary}

Retrieved context for personalization:
{chr(10).join(retrieved_context_lines) if retrieved_context_lines else '- No retrieved context available'}
""".strip()