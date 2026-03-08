from __future__ import annotations

import argparse
import json
import time
from collections import OrderedDict
from datetime import datetime
from typing import Any, Dict, List, Optional

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
        cached = dict(value)
        cached["cache_hit"] = "true"
        return cached

    def _set_cached_result(self, user_query: str, result: Dict[str, Any]) -> None:
        if not ENABLE_PIPELINE_CACHE:
            return
        key = self._normalize_query(user_query)
        self._query_cache[key] = dict(result)
        self._query_cache.move_to_end(key)
        while len(self._query_cache) > PIPELINE_CACHE_SIZE:
            self._query_cache.popitem(last=False)

    @staticmethod
    def _safe_json(value: Any) -> str:
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return json.dumps(str(value), ensure_ascii=False)

    def _profile_context(self, user_query: str) -> str:
        self.profile = self.behaviour.ensure_profile(self.user_id)
        return self.behaviour.build_runtime_context(self.profile, user_query=user_query)

    def run(self, user_query: str) -> Dict[str, Any]:
        cached = self._get_cached_result(user_query)
        if cached is not None:
            return cached

        total_start = time.perf_counter()
        timings: Dict[str, float] = {}
        stage_notes: List[str] = []

        t0 = time.perf_counter()
        profile_context = self._profile_context(user_query)
        timings["context_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        t0 = time.perf_counter()
        direct_match = self.remodeler.get_direct_answer_match(user_query)
        timings["direct_match_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        core_meta: Dict[str, Any] = {"answer": "", "answer_style": "", "risk_level": "low", "safety_notes": ""}
        remodel_meta: Dict[str, Any] = {}
        translator_meta: Dict[str, Any] = {}
        review_meta: Dict[str, Any] = {}
        route_taken = "full_pipeline"
        direct_answer_source = ""
        direct_answer_confidence = ""
        predicted_label = "unknown"
        risk_level = "low"

        if direct_match and direct_match.confidence >= DIRECT_MATCH_FORCE_THRESHOLD:
            raw_english = direct_match.answer
            remodeled_english = direct_match.answer
            route_taken = "dataset_direct_answer"
            direct_answer_source = f"{direct_match.match_type}:{direct_match.query}"
            direct_answer_confidence = f"{direct_match.confidence:.4f}"
            predicted_label = direct_match.label
            stage_notes.append("Used a high-confidence direct answer from the local dataset.")
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
            if remodel_meta.get("direct_answer_confidence") not in (None, ""):
                direct_answer_confidence = f"{float(remodel_meta.get('direct_answer_confidence', 0.0)):.4f}"

            for note in (core_meta.get("safety_notes"), remodel_meta.get("route_reason"), review_meta.get("review_note")):
                if str(note or "").strip():
                    stage_notes.append(str(note).strip())

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
            "review_meta": self._safe_json(review_meta),
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
    print(result.get("raw_english", ""))
    print("\n===== REMODELED ENGLISH =====")
    print(result.get("remodeled_english", ""))
    print("\n===== STANDARD TAMIL =====")
    print(result.get("tamil_text", ""))
    print("\n===== THENI TAMIL =====")
    print(result.get("theni_tamil_text", ""))
    print("\n===== ROUTE =====")
    print(result.get("route_taken", ""))
    if result.get("direct_answer_source"):
        print("\n===== DIRECT ANSWER HIT =====")
        print(result.get("direct_answer_source", ""))
        print(f"confidence={result.get('direct_answer_confidence', '')}")
    if result.get("predicted_label"):
        print("\n===== PREDICTED LABEL =====")
        print(result.get("predicted_label", ""))
    if result.get("risk_level"):
        print("\n===== RISK LEVEL =====")
        print(result.get("risk_level", ""))
    if result.get("stage_notes"):
        print("\n===== STAGE NOTES =====")
        print(result.get("stage_notes", ""))
    if result.get("translation_meta"):
        print("\n===== TRANSLATION META =====")
        print(result.get("translation_meta", ""))
    if result.get("timings_ms"):
        print("\n===== STAGE TIMINGS (ms) =====")
        print(result.get("timings_ms", ""))


def main() -> None:
    parser = argparse.ArgumentParser(description="Persona-aware English -> Tamil -> Theni Tamil pipeline")
    parser.add_argument("--user-id", default=DEFAULT_USER_ID, help="Unique user id for loading/storing profile")
    parser.add_argument("--rebuild-profile", action="store_true", help="Delete the current user profile and rebuild it")
    parser.add_argument("--prompt", default=DEFAULT_SINGLE_PROMPT, help="Run the pipeline once for a single prompt")
    parser.add_argument("--json", action="store_true", help="Print full JSON output for single-prompt mode")
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

    while True:
        try:
            prompt = input("\nAsk something (type 'exit' to quit): ").strip()
        except EOFError:
            break
        if not prompt or prompt.lower() in {"exit", "quit"}:
            break
        result = pipeline.run(prompt)
        if DEBUG:
            print_debug(result)
        else:
            print(result["theni_tamil_text"])


if __name__ == "__main__":
    main()