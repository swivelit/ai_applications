from __future__ import annotations

import string
from pathlib import Path
from typing import Dict, Any, Optional

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

from config import REMODEL_TEMPERATURE
from stage_openai_core import OpenAICore


class EmbeddedTextClassifier:
    """
    Trains a simple TF-IDF + Logistic Regression classifier
    from the local CSV dataset and predicts labels for text.
    """

    def __init__(self, dataset_path: Optional[str] = None) -> None:
        self.dataset_path = dataset_path or self._resolve_dataset_path()
        self.vectorizer = TfidfVectorizer()
        self.model = LogisticRegression(max_iter=1000)
        self.is_trained = False
        self.train_accuracy: Optional[float] = None
        self.test_accuracy: Optional[float] = None

        self._train()

    def _resolve_dataset_path(self) -> str:
        """
        Tries a few likely dataset locations.
        """
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
        text = str(text).lower()
        text = text.translate(str.maketrans("", "", string.punctuation))
        return text.strip()

    def _train(self) -> None:
        data = pd.read_csv(self.dataset_path)

        if "text" not in data.columns or "label" not in data.columns:
            raise ValueError(
                f"Dataset at {self.dataset_path} must contain 'text' and 'label' columns."
            )

        data = data.dropna(subset=["text", "label"]).copy()
        data["text"] = data["text"].apply(self.preprocess)

        X_train, X_test, y_train, y_test = train_test_split(
            data["text"],
            data["label"],
            test_size=0.2,
            random_state=42,
            stratify=data["label"] if data["label"].nunique() > 1 else None,
        )

        X_train_tfidf = self.vectorizer.fit_transform(X_train)
        X_test_tfidf = self.vectorizer.transform(X_test)

        self.model.fit(X_train_tfidf, y_train)

        self.train_accuracy = self.model.score(X_train_tfidf, y_train)
        self.test_accuracy = self.model.score(X_test_tfidf, y_test)
        self.is_trained = True

    def predict(self, text: str) -> str:
        if not self.is_trained:
            raise RuntimeError("Classifier is not trained.")

        cleaned_text = self.preprocess(text)
        input_vector = self.vectorizer.transform([cleaned_text])
        prediction = self.model.predict(input_vector)[0]
        return str(prediction)


class EnglishRemodeler:
    def __init__(self, core: OpenAICore, dataset_path: Optional[str] = None) -> None:
        self.core = core
        self.classifier = EmbeddedTextClassifier(dataset_path=dataset_path)

    def remodel(self, user_query: str, raw_answer: str, profile: Dict[str, Any]) -> str:
        profile_summary = profile.get("profile_summary", "")
        rules = profile.get("behaviour_rules", {})

        # Classify the user query so the remodel step can adapt slightly
        # without inventing anything.
        try:
            query_label = self.classifier.predict(user_query)
        except Exception:
            query_label = "unknown"

        system_prompt = (
            "You are an English remodel engine. "
            "Rewrite the answer so it sounds natural, safe, and personalized. "
            "Keep the meaning faithful. Do not invent facts. "
            "Respect health and food restrictions strictly."
        )

        user_prompt = f"""
User question:
{user_query}

Predicted query class:
{query_label}

Stored profile summary:
{profile_summary}

Behavior rules:
- Tone: {rules.get('preferred_tone')}
- Length: {rules.get('preferred_answer_length')}
- Avoid items: {', '.join(rules.get('avoid_items', [])) or 'none'}
- Avoid topics: {', '.join(rules.get('avoid_topics', [])) or 'none'}
- Mandatory notes: {' | '.join(rules.get('mandatory_notes', [])) or 'none'}

Raw English answer:
{raw_answer}

Task:
1. Rewrite the answer in polished English.
2. Make it align with the profile.
3. Use the predicted query class only as a soft personalization hint.
4. If the query is health-related, keep it cautious and non-dangerous.
5. Do not mention internal rules explicitly unless helpful.
6. Do not invent facts.
7. Output only final English text.
""".strip()

        return self.core.generate_text(
            system_prompt,
            user_prompt,
            temperature=REMODEL_TEMPERATURE,
            max_output_tokens=1000,
        )