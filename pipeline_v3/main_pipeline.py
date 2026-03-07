from __future__ import annotations

import argparse
import json
import time
from collections import OrderedDict
from datetime import datetime
from typing import Dict, Optional

from config import (
    DEBUG,
    DEFAULT_SINGLE_PROMPT,
    DEFAULT_USER_ID,
    ENABLE_PIPELINE_CACHE,
    LOGS_DIR,
    PIPELINE_CACHE_SIZE,
)
from stage_behaviour_questions import BehaviourQuestionnaire
from stage_english_remodel import EnglishRemodeler
from stage_openai_core import OpenAICore
from stage_translate import StageTranslator


class PersonaTamilPipeline:
    def __init__(self, user_id: str) -> None:
        self.user_id = user_id
        self.behaviour = BehaviourQuestionnaire()
        self.core = OpenAICore()
        self.remodeler = EnglishRemodeler(self.core)
        self.translator = StageTranslator(self.core)
        self.profile = self.behaviour.ensure_profile(user_id)
        self._query_cache: "OrderedDict[str, Dict[str, str]]" = OrderedDict()

    @staticmethod
    def _normalize_query(query: str) -> str:
        return " ".join(str(query or "").strip().lower().split())

    def _get_cached_result(self, user_query: str) -> Optional[Dict[str, str]]:
        if not ENABLE_PIPELINE_CACHE:
            return None
        key = self._normalize_query(user_query)
        value = self._query_cache.get(key)
        if value is None:
            return None
        self._query_cache.move_to_end(key)
        return dict(value)

    def _set_cached_result(self, user_query: str, result: Dict[str, str]) -> None:
        if not ENABLE_PIPELINE_CACHE:
            return
        key = self._normalize_query(user_query)
        self._query_cache[key] = dict(result)
        self._query_cache.move_to_end(key)
        while len(self._query_cache) > PIPELINE_CACHE_SIZE:
            self._query_cache.popitem(last=False)

    def run(self, user_query: str) -> Dict[str, str]:
        cached = self._get_cached_result(user_query)
        if cached is not None:
            cached["cache_hit"] = "true"
            return cached

        total_start = time.perf_counter()
        timings: Dict[str, float] = {}

        t0 = time.perf_counter()
        profile_context = self.behaviour.build_runtime_context(self.profile, user_query=user_query)
        timings["context_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        t0 = time.perf_counter()
        direct_match = self.remodeler.get_direct_answer_match(user_query)
        timings["direct_match_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        if direct_match and direct_match.confidence >= 0.84:
            raw_english = direct_match.answer
            remodeled_english = direct_match.answer
            direct_answer_source = f"{direct_match.match_type}:{direct_match.query}"
            direct_answer_confidence = f"{direct_match.confidence:.4f}"
            predicted_label = direct_match.label
        else:
            t0 = time.perf_counter()
            raw_english = self.core.answer_user_query(user_query, profile_context)
            timings["core_answer_ms"] = round((time.perf_counter() - t0) * 1000, 2)

            t0 = time.perf_counter()
            remodeled_english = self.remodeler.remodel(user_query, raw_english, self.profile)
            timings["remodel_ms"] = round((time.perf_counter() - t0) * 1000, 2)

            direct_answer_source = ""
            direct_answer_confidence = ""
            try:
                predicted_label = self.remodeler.classifier.predict(user_query)
            except Exception:
                predicted_label = "unknown"

        t0 = time.perf_counter()
        tamil_text = self.translator.english_to_tamil(remodeled_english, self.profile)
        timings["english_to_tamil_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        t0 = time.perf_counter()
        theni_tamil_text = self.translator.tamil_to_thenitamil(tamil_text)
        timings["tamil_to_theni_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        total_ms = round((time.perf_counter() - total_start) * 1000, 2)
        result = {
            "raw_english": raw_english,
            "remodeled_english": remodeled_english,
            "tamil_text": tamil_text,
            "theni_tamil_text": theni_tamil_text,
            "direct_answer_source": direct_answer_source,
            "direct_answer_confidence": direct_answer_confidence,
            "predicted_label": predicted_label,
            "cache_hit": "false",
            "timings_ms": json.dumps({**timings, "total_ms": total_ms}, ensure_ascii=False),
        }
        self._log_pipeline_run(user_query, result)
        self._set_cached_result(user_query, result)
        return result

    def _log_pipeline_run(self, user_query: str, result: Dict[str, str]) -> None:
        log_path = LOGS_DIR / f"{self.user_id}_history.jsonl"
        record = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "user_id": self.user_id,
            "query": user_query,
            "profile_summary": self.profile.get("profile_summary", ""),
            "profile_card": self.profile.get("profile_card", {}),
            "result": result,
        }
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def print_debug(result: Dict[str, str]) -> None:
    print("\n===== RAW ENGLISH =====")
    print(result["raw_english"])
    print("\n===== REMODELED ENGLISH =====")
    print(result["remodeled_english"])
    print("\n===== STANDARD TAMIL =====")
    print(result["tamil_text"])
    print("\n===== THENI TAMIL =====")
    print(result["theni_tamil_text"])

    if result.get("direct_answer_source"):
        print("\n===== DIRECT ANSWER HIT =====")
        print(result["direct_answer_source"])
        print(f"confidence={result.get('direct_answer_confidence', '')}")

    if result.get("predicted_label"):
        print("\n===== PREDICTED LABEL =====")
        print(result["predicted_label"])

    if result.get("timings_ms"):
        print("\n===== STAGE TIMINGS (ms) =====")
        print(result["timings_ms"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Persona-aware English -> Tamil -> Theni Tamil pipeline")
    parser.add_argument("--user-id", default=DEFAULT_USER_ID, help="Unique user id for loading/storing profile")
    parser.add_argument(
        "--rebuild-profile",
        action="store_true",
        help="Force profile recreation by deleting the current user profile first",
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_SINGLE_PROMPT,
        help="Optional single prompt mode. If provided, the pipeline runs once and exits.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="When used with --prompt, print the full JSON result instead of only Theni Tamil output.",
    )
    args = parser.parse_args()

    behaviour = BehaviourQuestionnaire()
    if args.rebuild_profile:
        profile_path = behaviour._profile_path(args.user_id)
        if profile_path.exists():
            profile_path.unlink()
            print(f"Deleted old profile: {profile_path.name}")

    pipeline = PersonaTamilPipeline(args.user_id)

    if args.prompt:
        result = pipeline.run(args.prompt)
        if args.json or DEBUG:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(result["theni_tamil_text"])
        return

    print("\nPipeline ready. Type your question below.")
    print("Type 'exit' to quit.\n")

    while True:
        user_query = input("You: ").strip()
        if not user_query:
            continue
        if user_query.lower() in {"exit", "quit"}:
            print("Goodbye.")
            break

        result = pipeline.run(user_query)
        if DEBUG:
            print_debug(result)
        else:
            print("\nAssistant (Theni Tamil):")
            print(result["theni_tamil_text"])
            print()


if __name__ == "__main__":
    main()