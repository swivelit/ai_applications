import argparse
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
    """
    Auto-pick which pipeline field to compare against.
    - If expected answer contains Tamil characters, compare with theni_tamil_text.
    - Otherwise compare with remodeled_english.
    """
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
    """
    Returns similarity percentage between 0 and 100.
    Uses RapidFuzz if available, else falls back to difflib.
    """
    expected_norm = normalize_text(expected)
    predicted_norm = normalize_text(predicted)

    if not expected_norm and not predicted_norm:
        return 100.0
    if not expected_norm or not predicted_norm:
        return 0.0

    if RAPIDFUZZ_AVAILABLE:
        ratio_1 = fuzz.ratio(expected_norm, predicted_norm)
        ratio_2 = fuzz.partial_ratio(expected_norm, predicted_norm)
        ratio_3 = fuzz.token_sort_ratio(
            token_sort_string(expected_norm),
            token_sort_string(predicted_norm),
        )
        # Weighted blend for a more stable score
        score = (0.45 * ratio_1) + (0.20 * ratio_2) + (0.35 * ratio_3)
        return round(float(score), 2)

    seq = SequenceMatcher(None, expected_norm, predicted_norm).ratio() * 100
    return round(float(seq), 2)


def load_test_data(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    df = pd.read_csv(csv_path)

    required_cols = ["question", "answer", "conditions"]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(
            f"Missing required columns in {csv_path.name}: {missing}. "
            f"Expected columns: {required_cols}"
        )

    df = df.fillna("")
    return df


def get_pipeline_for_user(
    user_id: str,
    pipeline_cache: Dict[str, PersonaTamilPipeline],
) -> PersonaTamilPipeline:
    if user_id not in pipeline_cache:
        pipeline_cache[user_id] = PersonaTamilPipeline(user_id=user_id)
    return pipeline_cache[user_id]


def resolve_user_id(condition_value: str, fallback_user_id: str) -> Tuple[str, str]:
    """
    Uses column 3 ('conditions') as the user/profile selector.
    If that profile does not exist, falls back to fallback_user_id.

    Returns:
        selected_user_id, note
    """
    condition_value = str(condition_value).strip()

    if condition_value:
        candidate = sanitize_user_id(condition_value)
        if profile_exists(candidate):
            return candidate, f"used condition profile '{candidate}'"
        return fallback_user_id, (
            f"condition profile '{candidate}' not found, "
            f"fell back to '{fallback_user_id}'"
        )

    return fallback_user_id, f"empty condition, used fallback profile '{fallback_user_id}'"


def evaluate_pipeline(
    csv_path: Path,
    fallback_user_id: str,
    forced_output_key: str = None,
    save_results: bool = True,
) -> Tuple[pd.DataFrame, float]:
    df = load_test_data(csv_path)

    pipeline_cache: Dict[str, PersonaTamilPipeline] = {}
    rows: List[Dict[str, str]] = []
    scores: List[float] = []

    print(f"\nLoaded {len(df)} test case(s) from: {csv_path}")
    print(f"Fallback user_id: {fallback_user_id}")

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

            if not predicted_answer:
                score = 0.0
                print("Warning: pipeline returned empty output for selected key.")
            else:
                score = similarity_score(expected_answer, predicted_answer)

            scores.append(score)

            print(f"Expected   : {expected_answer}")
            print(f"Predicted  : {predicted_answer}")
            print(f"Similarity : {score:.2f}%")

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
                    "profile_note": profile_note,
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
                    "profile_note": f"{profile_note}; error: {exc}",
                }
            )
            scores.append(0.0)

    results_df = pd.DataFrame(rows)
    accuracy = round(sum(scores) / len(scores), 2) if scores else 0.0

    if save_results:
        output_path = csv_path.parent / "test_results.csv"
        results_df.to_csv(output_path, index=False)
        print(f"\nDetailed results saved to: {output_path}")

    return results_df, accuracy


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Test the PersonaTamilPipeline using data/test_data.csv.\n"
            "Column 1: question\n"
            "Column 2: answer\n"
            "Column 3: conditions\n"
            "The script runs the pipeline, compares generated output with expected answers, "
            "and reports average similarity as accuracy."
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
        help=(
            "Fallback user_id/profile to use when a profile named by 'conditions' "
            "does not exist"
        ),
    )
    parser.add_argument(
        "--output-key",
        type=str,
        choices=["raw_english", "remodeled_english", "tamil_text", "theni_tamil_text"],
        default=None,
        help=(
            "Force which pipeline output field to compare. "
            "If omitted, the script auto-selects: "
            "English answers -> remodeled_english, Tamil answers -> theni_tamil_text"
        ),
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
            f"If the pipeline tries to create a new profile, it may ask interactive questions.\n"
            f"Create the profile first, or use an existing profile user_id."
        )

    try:
        results_df, accuracy = evaluate_pipeline(
            csv_path=csv_path,
            fallback_user_id=fallback_user_id,
            forced_output_key=args.output_key,
            save_results=not args.no_save,
        )

        print("\n==============================")
        print("FINAL TEST SUMMARY")
        print("==============================")
        print(f"Total test cases     : {len(results_df)}")
        print(f"Average accuracy     : {accuracy:.2f}%")

        if len(results_df) > 0:
            best_row = results_df.loc[results_df["similarity_percent"].idxmax()]
            worst_row = results_df.loc[results_df["similarity_percent"].idxmin()]

            print(f"Best similarity      : {best_row['similarity_percent']:.2f}% (row {int(best_row['row_number'])})")
            print(f"Worst similarity     : {worst_row['similarity_percent']:.2f}% (row {int(worst_row['row_number'])})")

    except Exception as exc:
        print(f"Fatal error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()