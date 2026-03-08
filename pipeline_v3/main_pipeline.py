from __future__ import annotations

import argparse
import json
import time
from collections import OrderedDict
from datetime import datetime
from typing import Any, Dict, Optional

from config import (
    DEBUG,
    DEFAULT_SINGLE_PROMPT,
    DEFAULT_USER_ID,
    DIRECT_MATCH_FORCE_THRESHOLD,
    ENABLE_PIPELINE_CACHE,
    LOGS_DIR,
    PIPELINE_CACHE_SIZE,
    PIPELINE_VERSION,
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
        self._query_cache: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()

    @staticmethod
    def _normalize_query(query: str) -> str:
        return " ".join(str(query or "").strip().lower().split())

    def _get_cached_result(self, user_query: str) -> Optional[Dict[str, Any]]:
        if not ENABLE_PIPELINE_CACHE:
            return None
        key = self._normalize_query(user_query)
        value = self._query_cache.get(key)
        if value is None:
            return None
        self._query_cache.move_to_end(key)
        return dict(value)

    def _set_cached_result(self, user_query: str, result: Dict[str, Any]) -> None:
        if not ENABLE_PIPELINE_CACHE:
            return
        key = self._normalize_query(user_query)
        self._query_cache[key] = dict(result)
        self._query_cache.move_to_end(key)
        while len(self._query_cache) > PIPELINE_CACHE_SIZE:
            self._query_cache.popitem(last=False)

    def _safe_json(self, value: Any) -> str:
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return json.dumps(str(value), ensure_ascii=False)

    def run(self, user_query: str) -> Dict[str, Any]:
        cached = self._get_cached_result(user_query)
        if cached is not None:
            cached["cache_hit"] = "true"
            return cached

        total_start = time.perf_counter()
        timings: Dict[str, float] = {}
        stage_notes: List[str] = []

        t0 = time.perf_counter()
        self.profile = self.behaviour.ensure_profile(self.user_id)
        profile_context = self.behaviour.build_runtime_context(self.profile, user_query=user_query)
        timings["context_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        t0 = time.perf_counter()
        direct_match = self.remodeler.get_direct_answer_match(user_query)
        timings["direct_match_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        core_meta: Dict[str, Any] = {
            "answer": "",
            "answer_style": "",
            "risk_level": "low",
            "safety_notes": "",
        }
        remodel_meta: Dict[str, Any] = {}
        translator_meta: Dict[str, Any] = {}
        route_taken = "full_pipeline"
        direct_answer_source = ""
        direct_answer_confidence = ""

        if direct_match and direct_match.confidence >= DIRECT_MATCH_FORCE_THRESHOLD:
            raw_english = direct_match.answer
            remodeled_english = direct_match.answer
            route_taken = "dataset_direct_answer"
            direct_answer_source = f"{direct_match.match_type}:{direct_match.query}"
            direct_answer_confidence = f"{direct_match.confidence:.4f}"
            predicted_label = direct_match.label
            risk_level = "low"
            stage_notes.append("Used a high-confidence direct answer from the dataset.")
        else:
            t0 = time.perf_counter()
            core_meta = self.core.answer_user_query_structured(user_query, profile_context)
            timings["core_answer_ms"] = round((time.perf_counter() - t0) * 1000, 2)
            raw_english = str(core_meta.get("answer", "")).strip()

            t0 = time.perf_counter()
            remodel_meta = self.remodeler.remodel_with_meta(user_query, raw_english, self.profile)
            timings["remodel_ms"] = round((time.perf_counter() - t0) * 1000, 2)
            remodeled_english = str(remodel_meta.get("answer", raw_english)).strip() or raw_english

            t0 = time.perf_counter()
            review_meta = self.core.review_answer(user_query, remodeled_english, profile_context)
            timings["review_ms"] = round((time.perf_counter() - t0) * 1000, 2)
            remodeled_english = str(review_meta.get("final_answer", remodeled_english)).strip() or remodeled_english

            route_taken = str(remodel_meta.get("route", "full_rewrite"))
            predicted_label = str(remodel_meta.get("predicted_label", "unknown"))
            risk_level = str(remodel_meta.get("risk_level") or core_meta.get("risk_level") or "low")
            direct_answer_source = str(remodel_meta.get("direct_answer_source", ""))
            direct_answer_confidence = (
                f"{float(remodel_meta.get('direct_answer_confidence', 0.0)):.4f}"
                if remodel_meta.get("direct_answer_confidence") not in (None, "")
                else ""
            )

            if core_meta.get("safety_notes"):
                stage_notes.append(str(core_meta.get("safety_notes")))
            if remodel_meta.get("route_reason"):
                stage_notes.append(str(remodel_meta.get("route_reason")))
            if review_meta.get("review_note"):
                stage_notes.append(str(review_meta.get("review_note")))

        t0 = time.perf_counter()
        translator_meta = self.translator.english_to_tamil_with_meta(remodeled_english, self.profile)
        tamil_text = str(translator_meta.get("tamil_text", "")).strip()
        timings["english_to_tamil_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        t0 = time.perf_counter()
        theni_tamil_text = self.translator.tamil_to_thenitamil(tamil_text)
        timings["tamil_to_theni_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        total_ms = round((time.perf_counter() - total_start) * 1000, 2)
        result: Dict[str, Any] = {
            "pipeline_version": PIPELINE_VERSION,
            "raw_english": raw_english,
            "remodeled_english": remodeled_english,
            "tamil_text": tamil_text,
            "theni_tamil_text": theni_tamil_text,
            "direct_answer_source": direct_answer_source,
            "direct_answer_confidence": direct_answer_confidence,
            "predicted_label": predicted_label,
            "risk_level": risk_level,
            "route_taken": route_taken,
            "cache_hit": "false",
            "stage_notes": self._safe_json(stage_notes),
            "core_meta": self._safe_json(core_meta),
            "remodel_meta": self._safe_json(remodel_meta),
            "translation_meta": self._safe_json(translator_meta),
            "timings_ms": json.dumps({**timings, "total_ms": total_ms}, ensure_ascii=False),
        }
        self._log_pipeline_run(user_query, result)
        self._set_cached_result(user_query, result)
        return result

    def _log_pipeline_run(self, user_query: str, result: Dict[str, Any]) -> None:
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


def print_debug(result: Dict[str, Any]) -> None:
    print("\n===== PIPELINE VERSION =====")
    print(result.get("pipeline_version", ""))
    print("\n===== RAW ENGLISH =====")
    print(result["raw_english"])
    print("\n===== REMODELED ENGLISH =====")
    print(result["remodeled_english"])
    print("\n===== STANDARD TAMIL =====")
    print(result["tamil_text"])
    print("\n===== THENI TAMIL =====")
    print(result["theni_tamil_text"])

    print("\n===== ROUTE =====")
    print(result.get("route_taken", ""))

    if result.get("direct_answer_source"):
        print("\n===== DIRECT ANSWER HIT =====")
        print(result["direct_answer_source"])
        print(f"confidence={result.get('direct_answer_confidence', '')}")

    if result.get("predicted_label"):
        print("\n===== PREDICTED LABEL =====")
        print(result["predicted_label"])

    if result.get("risk_level"):
        print("\n===== RISK LEVEL =====")
        print(result["risk_level"])

    if result.get("stage_notes"):
        print("\n===== STAGE NOTES =====")
        print(result["stage_notes"])

    if result.get("translation_meta"):
        print("\n===== TRANSLATION META =====")
        print(result["translation_meta"])

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