# tamil_command_executor.py
# Full working code with:
# ✅ create folder
# ✅ save output as TEXT + JSON
# ✅ timestamped filenames (no overwrite)
# ✅ JSONL execution logging
# ✅ Windows-safe folder creation (handles file-vs-folder)

import os
import json
from datetime import datetime
from dataclasses import dataclass, asdict


# -----------------------------
# Parsed command structure
# -----------------------------
@dataclass
class ParsedCommand:
    original_text_ta: str
    translated_text_en: str
    action: str
    entity: str
    folder_name: str
    context: str = "unknown"
    confidence: float = 0.9


# -----------------------------
# Helpers
# -----------------------------
def make_run_id() -> str:
    # Example: 20260206_124012
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


# -----------------------------
# Logging (JSONL)
# -----------------------------
def log_execution(cmd: ParsedCommand, exec_result: dict, log_file: str = "./logs/executions.jsonl"):
    ensure_dir(os.path.dirname(log_file))

    record = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "command": asdict(cmd),
        "execution": exec_result
    }

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# -----------------------------
# Output saving
# -----------------------------
def save_text_output(folder_path: str, text: str, filename: str = "result.txt") -> str:
    file_path = os.path.join(folder_path, filename)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(text)
    return os.path.abspath(file_path)


def save_json_output(folder_path: str, data: dict, filename: str = "output.json") -> str:
    file_path = os.path.join(folder_path, filename)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return os.path.abspath(file_path)


# -----------------------------
# Execute: create folder (safe)
# -----------------------------
def create_folder(folder_name: str, base_dir: str = "./output") -> dict:
    ensure_dir(base_dir)
    folder_path = os.path.join(base_dir, folder_name)

    # If something exists at folder_path but it's a FILE, fail clearly.
    if os.path.exists(folder_path) and not os.path.isdir(folder_path):
        raise Exception(
            f"'{folder_path}' exists but is a FILE. Delete/rename it, then re-run."
        )

    ensure_dir(folder_path)

    return {
        "status": "success",
        "message": f"Folder created or already exists: {folder_name}",
        "path": os.path.abspath(folder_path)
    }


# -----------------------------
# (Optional) Simple folder-name extraction
# -----------------------------
def extract_folder_name(tamil_text: str) -> str:
    t = tamil_text.lower()

    # block common shell commands typed by mistake
    if t.startswith(("dir", "cd", "ls", "pwd")):
        return "work"

    if "வேலை" in t or "work" in t:
        return "work"
    if "வீடு" in t or "home" in t:
        return "Home Documents"
    if "ஆவணம்" in t or "document" in t or "documents" in t:
        return "Home Documents"

    return "New Folder"


# -----------------------------
# Demo run
# -----------------------------
if __name__ == "__main__":
    print("Tamil Execution System (Folder Create Demo)")
    tamil_text = input("Tamil command (example: என் வேலைக்காக ஒரு கோப்புறை உருவாக்கு): ").strip()

    folder_name = extract_folder_name(tamil_text)

    cmd = ParsedCommand(
        original_text_ta=tamil_text,
        translated_text_en="(translation optional)",
        action="create",
        entity="folder",
        folder_name=folder_name,
        context="unknown",
        confidence=0.9
    )

    # 1) Execute
    result = create_folder(cmd.folder_name)

    # 2) Save outputs (timestamped files)
    run_id = make_run_id()
    output_text = f"Execution completed.\nFolder: {cmd.folder_name}\nRunId: {run_id}\nTime(UTC): {datetime.utcnow().isoformat()}Z\n"

    text_file = save_text_output(result["path"], output_text, filename=f"result_{run_id}.txt")
    json_file = save_json_output(result["path"], result, filename=f"output_{run_id}.json")

    # Attach output paths into result (so they appear in executions.jsonl too)
    result["saved_text"] = text_file
    result["saved_json"] = json_file
    result["run_id"] = run_id

    # 3) Log
    log_execution(cmd, result)

    # 4) Print
    print("\n✅ Execution Done")
    print(result["message"])
    print("📂 Folder saved at:", result["path"])
    print("💾 Text output saved at:", text_file)
    print("💾 JSON output saved at:", json_file)
    print("🧾 Log saved at:", os.path.abspath("./logs/executions.jsonl"))
