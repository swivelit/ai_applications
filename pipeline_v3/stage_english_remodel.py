from __future__ import annotations

import csv
import math
import re
import string
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

from config import (
    DIRECT_MATCH_SEMANTIC_THRESHOLD,
    DIRECT_MATCH_STRONG_THRESHOLD,
    DIRECT_MATCH_WEAK_THRESHOLD,
    HEALTH_RISK_KEYWORDS,
    REMODEL_TEMPERATURE,
)
from stage_openai_core import OpenAICore


# ---------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------


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
    """Load broken CSVs where answers contain unquoted commas.

    Expected logical columns are: text, label, answer.
    If extra commas exist, everything after the label is merged back into answer.
    """
    rows: List[Dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if not header:
            return pd.DataFrame(columns=["text", "label", "answer"])

        for raw_row in reader:
            if not raw_row:
                continue
            if len(raw_row) < 2:
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


# ---------------------------------------------------------------------
# Classifier + direct answer engine
# ---------------------------------------------------------------------


class EmbeddedTextClassifier:
    """TF-IDF classifier + multi-strategy direct answer retrieval."""

    def __init__(self, dataset_path: Optional[str] = None) -> None:
        self.dataset_path = dataset_path or self._resolve_dataset_path()

        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 3),
            min_df=1,
            sublinear_tf=True,
        )
        self.model = LogisticRegression(max_iter=3000, class_weight="balanced")

        self.qa_vectorizer = TfidfVectorizer(
            ngram_range=(1, 3),
            min_df=1,
            sublinear_tf=True,
        )
        self.qa_matrix = None

        self.is_trained = False
        self.train_accuracy: Optional[float] = None
        self.test_accuracy: Optional[float] = None
        self.label_distribution: Dict[str, int] = {}
        self.raw_dataset: Optional[pd.DataFrame] = None
        self.dataset_summary: Dict[str, Any] = {}

        self.direct_answer_map: Dict[str, DirectAnswerMatch] = {}
        self.qa_records: List[Dict[str, str]] = []

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

        raise FileNotFoundError(
            "Could not find classifier dataset. Expected one of:\n"
            "- data/classifier_dataset.csv\n"
            "- classifier_dataset.csv\n"
            "- data/dataset.csv\n"
            "- dataset.csv"
        )

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
            raise ValueError(
                f"Dataset at {self.dataset_path} must contain 'text' and 'label' columns."
            )

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
        self.label_distribution = data["label"].value_counts().to_dict()
        self.dataset_summary = {
            "rows": int(len(data)),
            "labels": sorted(map(str, data["label"].unique().tolist())),
            "has_answers": int((data["answer"].str.strip() != "").sum()),
        }

        self.direct_answer_map = {}
        self.qa_records = []

        for _, row in data.iterrows():
            text = row["text"].strip()
            clean_text = row["clean_text"].strip()
            label = row["label"].strip()
            answer = row["answer"].strip()
            if not text or not clean_text:
                continue

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
            self.train_accuracy = 1.0
            self.test_accuracy = None
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
        X_test_tfidf = self.vectorizer.transform(X_test)

        self.model.fit(X_train_tfidf, y_train)
        self.train_accuracy = float(self.model.score(X_train_tfidf, y_train))
        self.test_accuracy = float(self.model.score(X_test_tfidf, y_test))
        self.is_trained = True

    def predict(self, text: str) -> str:
        if not self.is_trained:
            raise RuntimeError("Classifier is not trained.")
        cleaned_text = self.preprocess(text)
        input_vector = self.vectorizer.transform([cleaned_text])
        prediction = self.model.predict(input_vector)[0]
        return str(prediction)

    def predict_proba_map(self, text: str) -> Dict[str, float]:
        if not self.is_trained:
            raise RuntimeError("Classifier is not trained.")

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

    def get_direct_answer(self, text: str) -> Optional[str]:
        match = self.get_direct_answer_match(text)
        return match.answer if match else None


# ---------------------------------------------------------------------
# Advanced local RAG
# ---------------------------------------------------------------------


class AdvancedLocalRAG:
    def __init__(self, documents: List[Dict[str, Any]]) -> None:
        self.documents = documents or []
        self.stopwords = {
            "a", "an", "the", "and", "or", "but", "if", "to", "for", "of", "in", "on",
            "at", "by", "with", "from", "as", "is", "are", "was", "were", "be", "been",
            "this", "that", "these", "those", "it", "its", "into", "about", "your", "you",
            "user", "question", "answer", "profile", "assistant", "most", "best", "usually",
            "right", "now", "how", "what", "which", "when", "do", "does", "can", "should",
            "would", "could", "one", "two", "three", "only",
        }
        self.synonyms = {
            "greeting": ["hi", "hello", "vanakkam", "hey"],
            "health": ["wellness", "medical", "diet", "safe", "safety"],
            "food": ["meal", "eat", "diet", "snack", "recipe"],
            "urgent": ["emergency", "immediately", "danger", "severe"],
            "career": ["job", "work", "business", "professional"],
            "short": ["brief", "direct", "concise"],
            "detailed": ["explain", "structured", "steps"],
            "pregnancy": ["pregnant", "postpartum", "breastfeeding", "conceive"],
            "sugar": ["diabetes", "sweet", "glucose"],
        }
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)
        self.doc_texts = [self._normalize(doc.get("text", "")) for doc in self.documents]
        self.doc_tokens = [self._tokenize(text) for text in self.doc_texts]
        self.doc_matrix = self.vectorizer.fit_transform(self.doc_texts) if self.doc_texts else None

    @staticmethod
    def _normalize(text: Any) -> str:
        return _normalize_text(text)

    def _tokenize(self, text: Any) -> List[str]:
        normalized = self._normalize(text)
        return [t for t in normalized.split() if t and t not in self.stopwords]

    def _expand_query(self, query: str) -> str:
        tokens = self._tokenize(query)
        expanded = list(tokens)
        token_set = set(tokens)

        for token in list(tokens):
            if token in self.synonyms:
                expanded.extend(self.synonyms[token])

        for key, values in self.synonyms.items():
            if token_set.intersection(values):
                expanded.append(key)
                expanded.extend(values)

        return " ".join(expanded)

    @staticmethod
    def _jaccard(tokens1: List[str], tokens2: List[str]) -> float:
        s1, s2 = set(tokens1), set(tokens2)
        if not s1 or not s2:
            return 0.0
        return len(s1 & s2) / max(len(s1 | s2), 1)

    @staticmethod
    def _cosine_dense(v1, v2) -> float:
        numerator = float(v1.multiply(v2).sum())
        denom = math.sqrt(float(v1.multiply(v1).sum())) * math.sqrt(float(v2.multiply(v2).sum()))
        if denom == 0:
            return 0.0
        return numerator / denom

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 6,
        predicted_label: Optional[str] = None,
        label_probs: Optional[Dict[str, float]] = None,
        mmr_lambda: float = 0.80,
        min_score: float = 0.03,
    ) -> List[Dict[str, Any]]:
        if not self.documents or self.doc_matrix is None:
            return []

        expanded_query = self._expand_query(query)
        query_vec = self.vectorizer.transform([expanded_query])
        query_tokens = self._tokenize(expanded_query)

        scored: List[Tuple[int, float]] = []
        for idx, doc in enumerate(self.documents):
            semantic = self._cosine_dense(query_vec, self.doc_matrix[idx])
            lexical = self._jaccard(query_tokens, self.doc_tokens[idx])
            meta = doc.get("metadata", {})
            label = str(meta.get("label", ""))
            kind = str(meta.get("kind", ""))
            label_boost = 0.0
            kind_boost = 0.0

            if predicted_label and label and label == predicted_label:
                label_boost += 0.08
            if label_probs and label:
                label_boost += 0.10 * float(label_probs.get(label, 0.0))
            if kind in {"profile_rule", "label_summary", "profile_summary", "health_rule"}:
                kind_boost += 0.03
            if kind == "dataset_direct_answer":
                kind_boost += 0.04

            score = (0.66 * semantic) + (0.20 * lexical) + label_boost + kind_boost
            if score >= min_score:
                scored.append((idx, score))

        if not scored:
            return []

        scored.sort(key=lambda item: item[1], reverse=True)
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
                    diversity_penalty = max(self._cosine_dense(self.doc_matrix[idx], self.doc_matrix[s_idx]) for s_idx in selected)
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
# English remodeler
# ---------------------------------------------------------------------


class EnglishRemodeler:
    def __init__(self, core: OpenAICore, dataset_path: Optional[str] = None) -> None:
        self.core = core
        self.classifier = EmbeddedTextClassifier(dataset_path=dataset_path)
        self.dataset_path = self.classifier.dataset_path
        self.rag = AdvancedLocalRAG(self._build_rag_documents())
        self._remodel_cache: Dict[Tuple[str, str, str], str] = {}

    def get_direct_answer_match(self, user_query: str) -> Optional[DirectAnswerMatch]:
        return self.classifier.get_direct_answer_match(user_query)

    def has_direct_answer(self, user_query: str) -> bool:
        return self.get_direct_answer_match(user_query) is not None

    def get_direct_answer(self, user_query: str) -> Optional[str]:
        match = self.get_direct_answer_match(user_query)
        return match.answer if match else None

    def _load_dataset(self) -> pd.DataFrame:
        return self.classifier._load_dataset()

    def _build_rag_documents(self) -> List[Dict[str, Any]]:
        docs: List[Dict[str, Any]] = []
        data = self._load_dataset()

        label_examples: Dict[str, List[str]] = defaultdict(list)
        label_answers: Dict[str, List[str]] = defaultdict(list)

        for idx, row in data.iterrows():
            text = str(row["text"]).strip()
            label = str(row["label"]).strip()
            answer = str(row["answer"]).strip()

            docs.append(
                {
                    "doc_id": f"dataset::{idx}",
                    "text": f"User example query: {text}. Label: {label}.",
                    "metadata": {"kind": "dataset_example", "label": label},
                }
            )
            label_examples[label].append(text)

            if answer:
                docs.append(
                    {
                        "doc_id": f"dataset_answer::{idx}",
                        "text": f"Known query-answer pair. Query: {text}. Stored answer: {answer}. Label: {label}.",
                        "metadata": {"kind": "dataset_direct_answer", "label": label},
                    }
                )
                label_answers[label].append(answer)

        for label, examples in label_examples.items():
            docs.append(
                {
                    "doc_id": f"label_summary::{label}",
                    "text": (
                        f"Label {label} summary. Representative queries: {' | '.join(examples[:8])}. "
                        f"Representative answers: {' | '.join(label_answers.get(label, [])[:4])}. "
                        f"This label has {len(examples)} examples."
                    ),
                    "metadata": {"kind": "label_summary", "label": label},
                }
            )

        docs.extend(
            [
                {
                    "doc_id": "rule::health_safety",
                    "text": (
                        "For health-related queries, rewrite cautiously. Do not prescribe medicine. Do not overclaim. "
                        "Suggest qualified medical support for diagnosis, emergencies, severe symptoms, pregnancy-related risk, diabetes, "
                        "blood pressure, allergy, kidney concerns, or medication changes."
                    ),
                    "metadata": {"kind": "health_rule", "label": "safety"},
                },
                {
                    "doc_id": "rule::faithfulness",
                    "text": (
                        "Remodeling must preserve the meaning of the raw answer. Improve clarity, grammar, structure, and personalization, "
                        "but do not invent facts."
                    ),
                    "metadata": {"kind": "profile_rule", "label": "faithfulness"},
                },
                {
                    "doc_id": "rule::tone_length",
                    "text": (
                        "Assistant should align wording to the user's preferred tone and answer length. "
                        "Possible tone preferences include warm, respectful, short direct, detailed, and friendly casual."
                    ),
                    "metadata": {"kind": "profile_rule", "label": "tone"},
                },
            ]
        )
        return docs

    @staticmethod
    def _safe_join(items: List[str], default: str = "none") -> str:
        cleaned = [str(item).strip() for item in items if str(item).strip()]
        return ", ".join(cleaned) if cleaned else default

    def _extract_profile_snippets(self, profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        answers = profile.get("answers", {}) or {}
        rules = profile.get("behaviour_rules", {}) or {}
        snippets: List[Dict[str, Any]] = []

        def add(doc_id: str, text: str, kind: str = "profile_rule", label: str = "profile") -> None:
            snippets.append({"doc_id": doc_id, "text": text, "metadata": {"kind": kind, "label": label}})

        add("profile::summary", f"Stored profile summary: {profile.get('profile_summary', '')}", kind="profile_summary")
        add(
            "profile::tone_length",
            f"Preferred tone is {rules.get('preferred_tone', 'warm and clear')}. Preferred answer length is {rules.get('preferred_answer_length', '1-2 paragraphs')}.",
        )
        add(
            "profile::avoid",
            f"Avoid items: {self._safe_join(rules.get('avoid_items', []))}. Avoid topics: {self._safe_join(rules.get('avoid_topics', []))}.",
        )
        add("profile::mandatory_notes", f"Mandatory notes: {self._safe_join(rules.get('mandatory_notes', []))}.")
        add("profile::style_bias", f"Response style bias: {self._safe_join(rules.get('response_style_bias', []))}.")

        rag_hints = profile.get("rag_personality_hints", {}) or {}
        if rag_hints:
            add(
                "profile::personality_hints",
                f"Retrieved personality hints: top traits are {self._safe_join(rag_hints.get('top_traits', []))}. {rag_hints.get('personality_summary', '')}",
                kind="profile_personality",
            )

        add(
            "profile::answers",
            (
                f"Life stage: {answers.get('life_stage', '')}. Food preference: {answers.get('food_preference', '')}. "
                f"Health conditions: {self._safe_join(answers.get('health_conditions', []))}. Food caution: {answers.get('food_caution', '')}. "
                f"Personality style: {answers.get('personality_style', '')}. Stress support: {answers.get('stress_support', '')}. "
                f"Communication tone: {answers.get('communication_tone', '')}. Answer length: {answers.get('answer_length', '')}. "
                f"Hobbies: {self._safe_join(answers.get('hobbies', []))}. Main goal: {answers.get('main_goal', '')}. Family role: {answers.get('family_role', '')}."
            ),
            kind="profile_answers",
        )
        return snippets

    def _build_runtime_rag(self, profile: Dict[str, Any], raw_answer: str) -> AdvancedLocalRAG:
        runtime_docs = list(self.rag.documents)
        runtime_docs.extend(self._extract_profile_snippets(profile))
        runtime_docs.append(
            {
                "doc_id": "runtime::raw_answer",
                "text": f"Raw answer to preserve faithfully: {raw_answer}",
                "metadata": {"kind": "raw_answer", "label": "raw_answer"},
            }
        )
        return AdvancedLocalRAG(runtime_docs)

    def _format_retrieved_docs(self, docs: List[Dict[str, Any]]) -> str:
        if not docs:
            return "- No retrieved grounding snippets found."
        lines = []
        for item in docs:
            meta = item.get("metadata", {})
            lines.append(f"- [{meta.get('kind', 'unknown')}] {item.get('text', '')} (score={item.get('retrieval_score', 0.0)})")
        return "\n".join(lines)

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

    def remodel(self, user_query: str, raw_answer: str, profile: Dict[str, Any]) -> str:
        direct_match = self.get_direct_answer_match(user_query)
        if direct_match and direct_match.confidence >= DIRECT_MATCH_SEMANTIC_THRESHOLD:
            return direct_match.answer

        profile_summary = profile.get("profile_summary", "")
        rules = profile.get("behaviour_rules", {}) or {}
        cache_key = (_normalize_text(user_query), _normalize_text(raw_answer), _normalize_text(profile_summary))
        cached = self._remodel_cache.get(cache_key)
        if cached:
            return cached

        try:
            query_label = self.classifier.predict(user_query)
        except Exception:
            query_label = "unknown"

        try:
            label_probs = self.classifier.predict_proba_map(user_query)
        except Exception:
            label_probs = {query_label: 1.0} if query_label != "unknown" else {}

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
                query_label,
            ]
        ).strip()

        runtime_rag = self._build_runtime_rag(profile, raw_answer)
        retrieved_docs = runtime_rag.retrieve(
            retrieval_query,
            top_k=8,
            predicted_label=query_label,
            label_probs=label_probs,
            min_score=0.02,
        )

        health_sensitive = self._is_health_sensitive(user_query + " " + raw_answer, profile)
        schema = {
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
                "applied_tone": {"type": "string"},
                "risk_level": {"type": "string", "enum": ["low", "medium", "high"]},
            },
            "required": ["answer", "applied_tone", "risk_level"],
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

Predicted query class:
{query_label}

Predicted class probabilities:
{label_probs}

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
{self._format_retrieved_docs(retrieved_docs)}

Additional guidance:
- Health-sensitive topic: {'yes' if health_sensitive else 'no'}
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

        answer = self._post_process_answer(data.get("answer", ""))
        if not answer:
            answer = self._post_process_answer(raw_answer)

        weak_direct_match = self.get_direct_answer_match(user_query)
        if weak_direct_match and weak_direct_match.confidence >= DIRECT_MATCH_WEAK_THRESHOLD:
            # When a near-direct match exists, keep the stored answer as the single source of truth.
            answer = weak_direct_match.answer

        self._remodel_cache[cache_key] = answer
        return answer