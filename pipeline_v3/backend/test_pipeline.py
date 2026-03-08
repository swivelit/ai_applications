from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

from config import DATA_DIR, DEFAULT_USER_ID, PROFILES_DIR
from main_pipeline import PersonaTamilPipeline

try:
    from rapidfuzz import fuzz

    RAPIDFUZZ_AVAILABLE = True
except Exception:
    RAPIDFUZZ_AVAILABLE = False

from difflib import SequenceMatcher


def sanitize_user_id(value: str) -> str:
    value = str(value).strip()
    safe = "".join(ch for ch in value if ch.isalnum() or ch in ("_", "-"))
    return safe or DEFAULT_USER_ID


def profile_exists(user_id: str) -> bool:
    return (PROFILES_DIR / f"{sanitize_user_id(user_id)}.json").exists()


def normalize_text(text: str) -> str:
    if text is None:
        return ""
    text = str(text)
    text = unicodedata.normalize("NFKC", text)
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def contains_tamil(text: str) -> bool:
    return bool(re.search(r"[\u0B80-\u0BFF]", str(text)))


def choose_output_key(expected_answer: str, forced_output_key: str = None) -> str:
    if forced_output_key:
        return forced_output_key
    if contains_tamil(expected_answer):
        return "theni_tamil_text"
    return "remodeled_english"


def token_sort_string(text: str) -> str:
    tokens = normalize_text(text).split()
    tokens.sort()
    return " ".join(tokens)


def similarity_score(expected: str, predicted: str) -> float:
    expected_norm = normalize_text(expected)
    predicted_norm = normalize_text(predicted)

    if not expected_norm and not predicted_norm:
        return 100.0
    if not expected_norm or not predicted_norm:
        return 0.0

    if RAPIDFUZZ_AVAILABLE:
        ratio_1 = fuzz.ratio(expected_norm, predicted_norm)
        ratio_2 = fuzz.partial_ratio(expected_norm, predicted_norm)
        ratio_3 = fuzz.token_sort_ratio(token_sort_string(expected_norm), token_sort_string(predicted_norm))
        score = (0.45 * ratio_1) + (0.20 * ratio_2) + (0.35 * ratio_3)
        return round(float(score), 2)

    seq = SequenceMatcher(None, expected_norm, predicted_norm).ratio() * 100
    return round(float(seq), 2)


def load_test_data(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    df = pd.read_csv(csv_path).fillna("")
    required_cols = ["question", "answer", "conditions"]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(
            f"Missing required columns in {csv_path.name}: {missing}. Expected columns: {required_cols}"
        )
    return df


def get_pipeline_for_user(user_id: str, pipeline_cache: Dict[str, PersonaTamilPipeline]) -> PersonaTamilPipeline:
    if user_id not in pipeline_cache:
        pipeline_cache[user_id] = PersonaTamilPipeline(user_id=user_id)
    return pipeline_cache[user_id]


def resolve_user_id(condition_value: str, fallback_user_id: str) -> Tuple[str, str]:
    condition_value = str(condition_value).strip()

    if condition_value:
        candidate = sanitize_user_id(condition_value)
        if profile_exists(candidate):
            return candidate, f"used condition profile '{candidate}'"
        return fallback_user_id, f"condition profile '{candidate}' not found, fell back to '{fallback_user_id}'"

    return fallback_user_id, f"empty condition, used fallback profile '{fallback_user_id}'"


def evaluate_pipeline(
    csv_path: Path,
    fallback_user_id: str,
    forced_output_key: str = None,
    save_results: bool = True,
    pass_threshold: float = 70.0,
) -> Tuple[pd.DataFrame, Dict[str, float]]:
    df = load_test_data(csv_path)

    pipeline_cache: Dict[str, PersonaTamilPipeline] = {}
    rows: List[Dict[str, str]] = []
    scores: List[float] = []

    print(f"\nLoaded {len(df)} test case(s) from: {csv_path}")
    print(f"Fallback user_id: {fallback_user_id}")
    print(f"Pass threshold: {pass_threshold:.2f}%")

    for index, row in df.iterrows():
        question = str(row["question"]).strip()
        expected_answer = str(row["answer"]).strip()
        condition = str(row["conditions"]).strip()

        if not question:
            print(f"\nSkipping row {index + 1}: empty question")
            continue

        user_id, profile_note = resolve_user_id(condition, fallback_user_id)
        output_key = choose_output_key(expected_answer, forced_output_key)

        print(f"\n--- Test Case {index + 1} ---")
        print(f"Question   : {question}")
        print(f"Condition  : {condition if condition else '(empty)'}")
        print(f"Profile    : {profile_note}")
        print(f"Compare key: {output_key}")

        try:
            pipeline = get_pipeline_for_user(user_id, pipeline_cache)
            result = pipeline.run(question)
            predicted_answer = str(result.get(output_key, "")).strip()
            stage_timings = result.get("timings_ms", "")
            direct_answer_source = result.get("direct_answer_source", "")
            predicted_label = result.get("predicted_label", "")

            if not predicted_answer:
                score = 0.0
                print("Warning: pipeline returned empty output for selected key.")
            else:
                score = similarity_score(expected_answer, predicted_answer)

            passed = score >= pass_threshold
            scores.append(score)

            print(f"Expected   : {expected_answer}")
            print(f"Predicted  : {predicted_answer}")
            print(f"Similarity : {score:.2f}%")
            print(f"Pass       : {'yes' if passed else 'no'}")

            rows.append(
                {
                    "row_number": index + 1,
                    "question": question,
                    "expected_answer": expected_answer,
                    "condition": condition,
                    "resolved_user_id": user_id,
                    "comparison_output_key": output_key,
                    "predicted_answer": predicted_answer,
                    "similarity_percent": score,
                    "passed": passed,
                    "profile_note": profile_note,
                    "direct_answer_source": direct_answer_source,
                    "predicted_label": predicted_label,
                    "timings_ms": stage_timings,
                    "error": "",
                }
            )
        except Exception as exc:
            print(f"Error in row {index + 1}: {exc}")
            rows.append(
                {
                    "row_number": index + 1,
                    "question": question,
                    "expected_answer": expected_answer,
                    "condition": condition,
                    "resolved_user_id": user_id,
                    "comparison_output_key": output_key,
                    "predicted_answer": "",
                    "similarity_percent": 0.0,
                    "passed": False,
                    "profile_note": profile_note,
                    "direct_answer_source": "",
                    "predicted_label": "",
                    "timings_ms": "",
                    "error": str(exc),
                }
            )
            scores.append(0.0)

    results_df = pd.DataFrame(rows)
    average_similarity = round(sum(scores) / len(scores), 2) if scores else 0.0
    pass_rate = round(float(results_df["passed"].mean() * 100), 2) if len(results_df) else 0.0
    summary = {
        "total_cases": float(len(results_df)),
        "average_similarity": average_similarity,
        "pass_rate": pass_rate,
        "best_similarity": round(float(results_df["similarity_percent"].max()), 2) if len(results_df) else 0.0,
        "worst_similarity": round(float(results_df["similarity_percent"].min()), 2) if len(results_df) else 0.0,
    }

    if save_results:
        output_path = csv_path.parent / "test_results.csv"
        summary_path = csv_path.parent / "test_summary.json"
        results_df.to_csv(output_path, index=False)
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"\nDetailed results saved to: {output_path}")
        print(f"Summary saved to: {summary_path}")

    return results_df, summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Test the PersonaTamilPipeline using data/test_data.csv.\n"
            "Column 1: question\n"
            "Column 2: answer\n"
            "Column 3: conditions\n"
            "The script runs the pipeline, compares generated output with expected answers, and reports similarity plus pass rate."
        )
    )
    parser.add_argument(
        "--csv-path",
        type=str,
        default=str(DATA_DIR / "test_data.csv"),
        help="Path to the test CSV file",
    )
    parser.add_argument(
        "--fallback-user-id",
        type=str,
        default=DEFAULT_USER_ID,
        help="Fallback user_id/profile to use when a profile named by 'conditions' does not exist",
    )
    parser.add_argument(
        "--output-key",
        type=str,
        choices=["raw_english", "remodeled_english", "tamil_text", "theni_tamil_text"],
        default=None,
        help=(
            "Force which pipeline output field to compare. If omitted, the script auto-selects: "
            "English answers -> remodeled_english, Tamil answers -> theni_tamil_text"
        ),
    )
    parser.add_argument(
        "--pass-threshold",
        type=float,
        default=70.0,
        help="Similarity score required for a row to count as pass",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not save detailed results to data/test_results.csv",
    )

    args = parser.parse_args()
    csv_path = Path(args.csv_path)
    fallback_user_id = sanitize_user_id(args.fallback_user_id)

    if not profile_exists(fallback_user_id):
        print(
            f"Warning: fallback profile '{fallback_user_id}' does not exist in {PROFILES_DIR}.\n"
            "If the pipeline tries to create a new profile, it may ask interactive questions.\n"
            "Create the profile first, or use an existing profile user_id."
        )

    try:
        results_df, summary = evaluate_pipeline(
            csv_path=csv_path,
            fallback_user_id=fallback_user_id,
            forced_output_key=args.output_key,
            save_results=not args.no_save,
            pass_threshold=args.pass_threshold,
        )

        print("\n==============================")
        print("FINAL TEST SUMMARY")
        print("==============================")
        print(f"Total test cases     : {int(summary['total_cases'])}")
        print(f"Average similarity   : {summary['average_similarity']:.2f}%")
        print(f"Pass rate            : {summary['pass_rate']:.2f}%")
        print(f"Best similarity      : {summary['best_similarity']:.2f}%")
        print(f"Worst similarity     : {summary['worst_similarity']:.2f}%")

        if len(results_df) > 0:
            best_row = results_df.loc[results_df["similarity_percent"].idxmax()]
            worst_row = results_df.loc[results_df["similarity_percent"].idxmin()]
            print(f"Best row             : {int(best_row['row_number'])}")
            print(f"Worst row            : {int(worst_row['row_number'])}")

    except Exception as exc:
        print(f"Fatal error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()