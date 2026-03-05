import argparse
import json
from datetime import datetime
from typing import Dict

from config import DEBUG, DEFAULT_USER_ID, LOGS_DIR
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

    def run(self, user_query: str) -> Dict[str, str]:
        profile_context = self.behaviour.build_runtime_context(self.profile)
        raw_english = self.core.answer_user_query(user_query, profile_context)
        remodeled_english = self.remodeler.remodel(user_query, raw_english, self.profile)
        tamil_text = self.translator.english_to_tamil(remodeled_english, self.profile)
        theni_tamil_text = self.translator.tamil_to_thenitamil(tamil_text)

        result = {
            "raw_english": raw_english,
            "remodeled_english": remodeled_english,
            "tamil_text": tamil_text,
            "theni_tamil_text": theni_tamil_text,
        }
        self._log_pipeline_run(user_query, result)
        return result

    def _log_pipeline_run(self, user_query: str, result: Dict[str, str]) -> None:
        log_path = LOGS_DIR / f"{self.user_id}_history.jsonl"
        record = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "user_id": self.user_id,
            "query": user_query,
            "profile_summary": self.profile.get("profile_summary", ""),
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Persona-aware English -> Tamil -> Theni Tamil pipeline")
    parser.add_argument("--user-id", default=DEFAULT_USER_ID, help="Unique user id for loading/storing profile")
    parser.add_argument(
        "--rebuild-profile",
        action="store_true",
        help="Force profile recreation by deleting the current user profile first",
    )
    args = parser.parse_args()

    behaviour = BehaviourQuestionnaire()
    if args.rebuild_profile:
        profile_path = behaviour._profile_path(args.user_id)
        if profile_path.exists():
            profile_path.unlink()
            print(f"Deleted old profile: {profile_path.name}")

    pipeline = PersonaTamilPipeline(args.user_id)

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