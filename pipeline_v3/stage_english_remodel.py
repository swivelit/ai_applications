from __future__ import annotations

import csv
import math
import re
import string
import unicodedata
from collections import Counter, OrderedDict, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

from config import (
    DIRECT_MATCH_ROUTE_THRESHOLD,
    DIRECT_MATCH_SEMANTIC_THRESHOLD,
    DIRECT_MATCH_STRONG_THRESHOLD,
    DIRECT_MATCH_WEAK_THRESHOLD,
    HEALTH_RISK_KEYWORDS,
    REMODEL_MIN_OUTPUT_CHARS,
    REMODEL_MIN_SIMILARITY_TO_RAW,
    REMODEL_TEMPERATURE,
)
from stage_openai_core import OpenAICore


def _normalize_text(text: Any) -> str:
    text = "" if text is None else str(text)
    text = unicodedata.normalize("NFKC", text).lower().strip()
    text = text.replace("_", " ").replace("-", " ")
    text = text.translate(str.maketrans("", "", string.punctuation))
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _tokenize(text: Any) -> List[str]:
    return [token for token in _normalize_text(text).split() if token]


def _jaccard_similarity(text1: str, text2: str) -> float:
    s1 = set(_tokenize(text1))
    s2 = set(_tokenize(text2))
    if not s1 or not s2:
        return 0.0
    return len(s1 & s2) / max(len(s1 | s2), 1)


def _sequence_similarity(text1: str, text2: str) -> float:
    from difflib import SequenceMatcher

    return float(SequenceMatcher(None, _normalize_text(text1), _normalize_text(text2)).ratio())


def _coerce_csv_rows(path: Path) -> pd.DataFrame:
    rows: List[Dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if not header:
            return pd.DataFrame(columns=["text", "label", "answer"])

        for raw_row in reader:
            if not raw_row or len(raw_row) < 2:
                continue
            text = raw_row[0].strip()
            label = raw_row[1].strip() if len(raw_row) > 1 else ""
            answer = ",".join(raw_row[2:]).strip() if len(raw_row) > 2 else ""
            rows.append({"text": text, "label": label, "answer": answer})

    return pd.DataFrame(rows, columns=["text", "label", "answer"])


@dataclass
class DirectAnswerMatch:
    query: str
    answer: str
    label: str
    confidence: float
    match_type: str


@dataclass
class RoutingDecision:
    route: str
    reason: str
    direct_match: Optional[DirectAnswerMatch]
    predicted_label: str
    label_probs: Dict[str, float]
    health_sensitive: bool
    raw_quality_score: float


class EmbeddedTextClassifier:
    def __init__(self, dataset_path: Optional[str] = None) -> None:
        self.dataset_path = dataset_path or self._resolve_dataset_path()
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 3), min_df=1, sublinear_tf=True)
        self.model = LogisticRegression(max_iter=3000, class_weight="balanced")
        self.qa_vectorizer = TfidfVectorizer(ngram_range=(1, 3), min_df=1, sublinear_tf=True)
        self.qa_matrix = None
        self.qa_records: List[Dict[str, str]] = []
        self.direct_answer_map: Dict[str, DirectAnswerMatch] = {}
        self.raw_dataset: Optional[pd.DataFrame] = None
        self.is_trained = False
        self._train()

    def _resolve_dataset_path(self) -> str:
        current_dir = Path(__file__).resolve().parent
        possible_paths = [
            current_dir / "data" / "classifier_dataset.csv",
            current_dir / "classifier_dataset.csv",
            current_dir / "data" / "dataset.csv",
            current_dir / "dataset.csv",
        ]
        for path in possible_paths:
            if path.exists():
                return str(path)
        raise FileNotFoundError("Could not find classifier dataset.")

    @staticmethod
    def preprocess(text: Any) -> str:
        return _normalize_text(text)

    def _load_dataset(self) -> pd.DataFrame:
        path = Path(self.dataset_path)
        try:
            data = pd.read_csv(path)
        except Exception:
            data = _coerce_csv_rows(path)

        if "text" not in data.columns or "label" not in data.columns:
            raise ValueError("Dataset must contain 'text' and 'label' columns.")

        if "answer" not in data.columns:
            data["answer"] = ""

        data = data.dropna(subset=["text", "label"]).copy()
        data["text"] = data["text"].astype(str)
        data["label"] = data["label"].astype(str)
        data["answer"] = data["answer"].fillna("").astype(str)
        data["clean_text"] = data["text"].apply(self.preprocess)
        data = data[data["clean_text"].str.len() > 0].copy()
        return data.reset_index(drop=True)

    def _train(self) -> None:
        data = self._load_dataset()
        self.raw_dataset = data.copy()

        self.qa_records = []
        self.direct_answer_map = {}
        for _, row in data.iterrows():
            text = str(row["text"]).strip()
            clean_text = str(row["clean_text"]).strip()
            label = str(row["label"]).strip()
            answer = str(row["answer"]).strip()
            if answer:
                match = DirectAnswerMatch(
                    query=text,
                    answer=answer,
                    label=label,
                    confidence=1.0,
                    match_type="exact",
                )
                self.direct_answer_map[clean_text] = match
                self.qa_records.append(
                    {
                        "text": text,
                        "clean_text": clean_text,
                        "label": label,
                        "answer": answer,
                    }
                )

        if self.qa_records:
            qa_corpus = [record["clean_text"] for record in self.qa_records]
            self.qa_matrix = self.qa_vectorizer.fit_transform(qa_corpus)

        if len(data) < 3 or data["label"].nunique() < 2:
            X = self.vectorizer.fit_transform(data["clean_text"])
            self.model.fit(X, data["label"])
            self.is_trained = True
            return

        label_counts = data["label"].value_counts()
        stratify_labels = data["label"] if label_counts.min() >= 2 else None
        X_train, X_test, y_train, y_test = train_test_split(
            data["clean_text"],
            data["label"],
            test_size=0.2,
            random_state=42,
            stratify=stratify_labels,
        )
        X_train_tfidf = self.vectorizer.fit_transform(X_train)
        self.model.fit(X_train_tfidf, y_train)
        self.is_trained = True

    def predict(self, text: str) -> str:
        cleaned_text = self.preprocess(text)
        input_vector = self.vectorizer.transform([cleaned_text])
        prediction = self.model.predict(input_vector)[0]
        return str(prediction)

    def predict_proba_map(self, text: str) -> Dict[str, float]:
        cleaned_text = self.preprocess(text)
        input_vector = self.vectorizer.transform([cleaned_text])

        if hasattr(self.model, "predict_proba"):
            probs = self.model.predict_proba(input_vector)[0]
            return {str(label): round(float(prob), 4) for label, prob in zip(self.model.classes_, probs)}

        label = self.predict(text)
        return {label: 1.0}

    @staticmethod
    def _cosine_dense(v1, v2) -> float:
        numerator = float(v1.multiply(v2).sum())
        denom = math.sqrt(float(v1.multiply(v1).sum())) * math.sqrt(float(v2.multiply(v2).sum()))
        if denom == 0:
            return 0.0
        return numerator / denom

    def _fuzzy_match(self, user_query: str) -> Optional[DirectAnswerMatch]:
        if not self.qa_records:
            return None

        best_record = None
        best_score = 0.0
        normalized_query = self.preprocess(user_query)

        for record in self.qa_records:
            seq = _sequence_similarity(normalized_query, record["clean_text"])
            jac = _jaccard_similarity(normalized_query, record["clean_text"])
            score = (0.70 * seq) + (0.30 * jac)
            if score > best_score:
                best_score = score
                best_record = record

        if best_record and best_score >= DIRECT_MATCH_STRONG_THRESHOLD:
            return DirectAnswerMatch(
                query=best_record["text"],
                answer=best_record["answer"],
                label=best_record["label"],
                confidence=round(best_score, 4),
                match_type="fuzzy",
            )
        return None

    def _semantic_match(self, user_query: str) -> Optional[DirectAnswerMatch]:
        if not self.qa_records or self.qa_matrix is None:
            return None

        cleaned_query = self.preprocess(user_query)
        query_vec = self.qa_vectorizer.transform([cleaned_query])

        best_idx = None
        best_score = 0.0
        for idx in range(self.qa_matrix.shape[0]):
            score = self._cosine_dense(query_vec, self.qa_matrix[idx])
            if score > best_score:
                best_score = score
                best_idx = idx

        if best_idx is None:
            return None

        record = self.qa_records[best_idx]
        lexical = _jaccard_similarity(cleaned_query, record["clean_text"])
        seq = _sequence_similarity(cleaned_query, record["clean_text"])
        final_score = (0.60 * best_score) + (0.20 * lexical) + (0.20 * seq)

        if final_score >= DIRECT_MATCH_SEMANTIC_THRESHOLD:
            return DirectAnswerMatch(
                query=record["text"],
                answer=record["answer"],
                label=record["label"],
                confidence=round(final_score, 4),
                match_type="semantic",
            )
        return None

    def get_direct_answer_match(self, text: str) -> Optional[DirectAnswerMatch]:
        normalized = self.preprocess(text)
        exact = self.direct_answer_map.get(normalized)
        if exact:
            return exact

        fuzzy = self._fuzzy_match(text)
        if fuzzy:
            return fuzzy

        semantic = self._semantic_match(text)
        if semantic:
            return semantic

        return None


class AdvancedLocalRAG:
    def __init__(self, documents: List[Dict[str, Any]]) -> None:
        self.documents = documents or []
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)
        self.doc_texts = [_normalize_text(doc.get("text", "")) for doc in self.documents]
        self.doc_matrix = self.vectorizer.fit_transform(self.doc_texts) if self.doc_texts else None

    @staticmethod
    def _jaccard(text1: str, text2: str) -> float:
        return _jaccard_similarity(text1, text2)

    @staticmethod
    def _cosine_dense(v1, v2) -> float:
        numerator = float(v1.multiply(v2).sum())
        denom = math.sqrt(float(v1.multiply(v1).sum())) * math.sqrt(float(v2.multiply(v2).sum()))
        if denom == 0:
            return 0.0
        return numerator / denom

    def retrieve(self, query: str, top_k: int = 6, min_score: float = 0.03) -> List[Dict[str, Any]]:
        if not self.documents or self.doc_matrix is None:
            return []

        cleaned_query = _normalize_text(query)
        query_vec = self.vectorizer.transform([cleaned_query])

        results: List[Tuple[int, float]] = []
        for idx, doc in enumerate(self.documents):
            semantic = self._cosine_dense(query_vec, self.doc_matrix[idx])
            lexical = self._jaccard(cleaned_query, self.doc_texts[idx])
            score = (0.72 * semantic) + (0.28 * lexical)
            if score >= min_score:
                results.append((idx, score))

        results.sort(key=lambda item: item[1], reverse=True)
        output: List[Dict[str, Any]] = []
        for idx, score in results[:top_k]:
            item = dict(self.documents[idx])
            item["retrieval_score"] = round(float(score), 4)
            output.append(item)
        return output


class EnglishRemodeler:
    def __init__(self, core: OpenAICore, dataset_path: Optional[str] = None) -> None:
        self.core = core
        self.classifier = EmbeddedTextClassifier(dataset_path=dataset_path)
        self.dataset_path = self.classifier.dataset_path
        self.rag = AdvancedLocalRAG(self._build_rag_documents())
        self._remodel_cache: "OrderedDict[Tuple[str, str, str], Dict[str, Any]]" = OrderedDict()

    def _build_rag_documents(self) -> List[Dict[str, Any]]:
        docs: List[Dict[str, Any]] = []
        data = self.classifier._load_dataset()

        for idx, row in data.iterrows():
            text = str(row.get("text", "")).strip()
            label = str(row.get("label", "")).strip()
            answer = str(row.get("answer", "")).strip()

            if text:
                docs.append(
                    {
                        "doc_id": f"dataset::query::{idx}",
                        "text": f"Dataset example query: {text}. Query label: {label}.",
                        "metadata": {"kind": "dataset_query", "label": label},
                    }
                )
            if answer:
                docs.append(
                    {
                        "doc_id": f"dataset::answer::{idx}",
                        "text": f"Dataset answer for label {label}. User intent: {text}. Suggested answer: {answer}.",
                        "metadata": {"kind": "dataset_direct_answer", "label": label},
                    }
                )

        docs.extend(
            [
                {
                    "doc_id": "rule::faithful_rewrite",
                    "text": "When rewriting, preserve meaning, keep useful structure, and do not add unsupported claims.",
                    "metadata": {"kind": "rewrite_rule", "label": "general"},
                },
                {
                    "doc_id": "rule::health_safety",
                    "text": "For health, pregnancy, medicine, diabetes, blood pressure, allergies, kidney issues, or emergencies, be cautious, avoid diagnosis-like certainty, and suggest a clinician for medication or urgent concerns.",
                    "metadata": {"kind": "health_rule", "label": "health"},
                },
                {
                    "doc_id": "rule::style",
                    "text": "Prefer concise, natural English that stays practical and aligned with the user's tone and answer-length preference.",
                    "metadata": {"kind": "style_rule", "label": "general"},
                },
            ]
        )
        return docs

    def get_direct_answer_match(self, user_query: str) -> Optional[DirectAnswerMatch]:
        return self.classifier.get_direct_answer_match(user_query)

    @staticmethod
    def _safe_join(items: List[str], default: str = "none") -> str:
        cleaned = [str(item).strip() for item in items if str(item).strip()]
        return ", ".join(cleaned) if cleaned else default

    @staticmethod
    def _is_health_sensitive(text: str, profile: Dict[str, Any]) -> bool:
        normalized = _normalize_text(text)
        if any(keyword in normalized for keyword in HEALTH_RISK_KEYWORDS):
            return True
        rules = profile.get("behaviour_rules", {}) or {}
        flags = rules.get("health_flags", {}) or {}
        return any(bool(value) for value in flags.values())

    @staticmethod
    def _post_process_answer(text: str) -> str:
        text = str(text or "").strip()
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text

    def _estimate_answer_quality(self, answer: str) -> float:
        answer = str(answer or "").strip()
        if not answer:
            return 0.0
        length_score = min(len(answer) / 180.0, 1.0)
        has_structure = 1.0 if any(token in answer for token in ["\n", ":", "1.", "- "]) else 0.4
        sentence_like = 1.0 if re.search(r"[.!?]", answer) else 0.5
        return round((0.45 * length_score) + (0.30 * has_structure) + (0.25 * sentence_like), 4)

    def decide_route(self, user_query: str, raw_answer: str, profile: Dict[str, Any]) -> RoutingDecision:
        direct_match = self.get_direct_answer_match(user_query)
        try:
            predicted_label = self.classifier.predict(user_query)
        except Exception:
            predicted_label = "unknown"
        try:
            label_probs = self.classifier.predict_proba_map(user_query)
        except Exception:
            label_probs = {predicted_label: 1.0} if predicted_label != "unknown" else {}

        health_sensitive = self._is_health_sensitive(f"{user_query} {raw_answer}", profile)
        raw_quality_score = self._estimate_answer_quality(raw_answer)

        if direct_match and direct_match.confidence >= DIRECT_MATCH_STRONG_THRESHOLD:
            return RoutingDecision(
                route="direct_answer",
                reason="high-confidence direct match from dataset",
                direct_match=direct_match,
                predicted_label=predicted_label,
                label_probs=label_probs,
                health_sensitive=health_sensitive,
                raw_quality_score=raw_quality_score,
            )

        if health_sensitive:
            return RoutingDecision(
                route="careful_rewrite",
                reason="health-sensitive request needs conservative polish",
                direct_match=direct_match,
                predicted_label=predicted_label,
                label_probs=label_probs,
                health_sensitive=health_sensitive,
                raw_quality_score=raw_quality_score,
            )

        if raw_quality_score >= 0.72:
            return RoutingDecision(
                route="light_rewrite",
                reason="raw answer is already decent; use light polish",
                direct_match=direct_match,
                predicted_label=predicted_label,
                label_probs=label_probs,
                health_sensitive=health_sensitive,
                raw_quality_score=raw_quality_score,
            )

        if direct_match and direct_match.confidence >= DIRECT_MATCH_ROUTE_THRESHOLD:
            return RoutingDecision(
                route="direct_answer",
                reason="semantic direct match is strong enough",
                direct_match=direct_match,
                predicted_label=predicted_label,
                label_probs=label_probs,
                health_sensitive=health_sensitive,
                raw_quality_score=raw_quality_score,
            )

        return RoutingDecision(
            route="full_rewrite",
            reason="use retrieval-grounded rewrite",
            direct_match=direct_match,
            predicted_label=predicted_label,
            label_probs=label_probs,
            health_sensitive=health_sensitive,
            raw_quality_score=raw_quality_score,
        )

    def _guard_answer(self, raw_answer: str, remodeled_answer: str, routing: RoutingDecision) -> str:
        raw_answer = self._post_process_answer(raw_answer)
        remodeled_answer = self._post_process_answer(remodeled_answer)

        if routing.direct_match and routing.direct_match.confidence >= DIRECT_MATCH_ROUTE_THRESHOLD:
            return routing.direct_match.answer

        if not remodeled_answer:
            return raw_answer

        if len(remodeled_answer) < REMODEL_MIN_OUTPUT_CHARS and raw_answer:
            return raw_answer

        if raw_answer:
            similarity = (0.55 * _jaccard_similarity(raw_answer, remodeled_answer)) + (
                0.45 * _sequence_similarity(raw_answer, remodeled_answer)
            )
            if similarity < REMODEL_MIN_SIMILARITY_TO_RAW:
                return raw_answer

        return remodeled_answer

    def remodel_with_meta(self, user_query: str, raw_answer: str, profile: Dict[str, Any]) -> Dict[str, Any]:
        profile_summary = profile.get("profile_summary", "")
        cache_key = (_normalize_text(user_query), _normalize_text(raw_answer), _normalize_text(profile_summary))
        cached = self._remodel_cache.get(cache_key)
        if cached is not None:
            self._remodel_cache.move_to_end(cache_key)
            return dict(cached)

        routing = self.decide_route(user_query, raw_answer, profile)

        if routing.route == "direct_answer" and routing.direct_match is not None:
            result = {
                "answer": routing.direct_match.answer,
                "route": routing.route,
                "route_reason": routing.reason,
                "predicted_label": routing.predicted_label,
                "label_probs": routing.label_probs,
                "risk_level": "high" if routing.health_sensitive else "low",
                "direct_answer_source": f"{routing.direct_match.match_type}:{routing.direct_match.query}",
                "direct_answer_confidence": round(float(routing.direct_match.confidence), 4),
                "retrieved_docs": [],
            }
            self._remodel_cache[cache_key] = dict(result)
            return result

        rules = profile.get("behaviour_rules", {}) or {}
        retrieval_query = " ".join(
            [
                user_query,
                raw_answer,
                profile_summary,
                str(rules.get("preferred_tone", "")),
                str(rules.get("preferred_answer_length", "")),
                " ".join(rules.get("avoid_items", []) or []),
                " ".join(rules.get("avoid_topics", []) or []),
                " ".join(rules.get("mandatory_notes", []) or []),
                " ".join(rules.get("response_style_bias", []) or []),
                routing.predicted_label,
            ]
        ).strip()

        retrieved_docs = self.rag.retrieve(retrieval_query, top_k=8, min_score=0.02)

        schema = {
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
                "applied_tone": {"type": "string"},
                "risk_level": {"type": "string", "enum": ["low", "medium", "high"]},
                "rewrite_intensity": {"type": "string", "enum": ["light", "medium", "strong"]},
            },
            "required": ["answer", "applied_tone", "risk_level", "rewrite_intensity"],
            "additionalProperties": False,
        }

        system_prompt = (
            "You are an advanced English remodel engine with retrieval grounding. Rewrite the raw answer into polished, natural, faithful English. "
            "Preserve meaning. Improve clarity, structure, tone fit, and safety. Do not invent facts, symptoms, diagnoses, or unsupported details. "
            "Respect profile constraints and retrieved grounding."
        )

        user_prompt = f"""
User question:
{user_query}

Raw English answer:
{raw_answer}

Routing decision:
- route: {routing.route}
- reason: {routing.reason}
- health-sensitive: {'yes' if routing.health_sensitive else 'no'}

Predicted query class:
{routing.predicted_label}

Predicted class probabilities:
{routing.label_probs}

Stored profile summary:
{profile_summary}

Behavior rules:
- Tone: {rules.get('preferred_tone')}
- Length: {rules.get('preferred_answer_length')}
- Avoid items: {self._safe_join(rules.get('avoid_items', []))}
- Avoid topics: {self._safe_join(rules.get('avoid_topics', []))}
- Mandatory notes: {self._safe_join(rules.get('mandatory_notes', []))}
- Response style bias: {self._safe_join(rules.get('response_style_bias', []))}

Retrieved grounding snippets:
{chr(10).join([f"- {item.get('text', '')}" for item in retrieved_docs])}

Additional guidance:
- If health-sensitive, stay cautious and avoid risky or diagnosis-like statements.
- If the answer is already strong, improve wording without changing substance.
- Prefer concise faithfulness over creativity.
- Output JSON following the schema.
""".strip()

        data = self.core.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema_name="english_remodel_result",
            schema=schema,
            temperature=REMODEL_TEMPERATURE,
            max_output_tokens=1000,
        )

        candidate_answer = self._post_process_answer(data.get("answer", "")) or self._post_process_answer(raw_answer)
        final_answer = self._guard_answer(raw_answer, candidate_answer, routing)

        result = {
            "answer": final_answer,
            "route": routing.route,
            "route_reason": routing.reason,
            "predicted_label": routing.predicted_label,
            "label_probs": routing.label_probs,
            "risk_level": str(data.get("risk_level", "high" if routing.health_sensitive else "low")),
            "direct_answer_source": "",
            "direct_answer_confidence": round(float(routing.direct_match.confidence), 4) if routing.direct_match else 0.0,
            "retrieved_docs": [
                {
                    "doc_id": item.get("doc_id", ""),
                    "kind": item.get("metadata", {}).get("kind", ""),
                    "score": item.get("retrieval_score", 0.0),
                }
                for item in retrieved_docs
            ],
            "rewrite_intensity": str(data.get("rewrite_intensity", "medium")),
            "applied_tone": str(data.get("applied_tone", rules.get("preferred_tone", ""))),
        }
        self._remodel_cache[cache_key] = dict(result)
        return result

    def remodel(self, user_query: str, raw_answer: str, profile: Dict[str, Any]) -> str:
        return str(self.remodel_with_meta(user_query, raw_answer, profile).get("answer", "")).strip()