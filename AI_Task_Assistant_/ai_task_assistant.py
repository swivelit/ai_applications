"""
AI Task Assistant – Single File Version

Supports:
- Meeting scheduling
- Reminders
- Alarms
- Task management
- Notes
- Messaging
- Information queries

Method:
Rule-based intent classification + spaCy entity extraction
"""

import spacy
from datetime import datetime

# Load spaCy English model
# Run once before execution:
# python -m spacy download en_core_web_sm
nlp = spacy.load("en_core_web_sm")


# -------------------------------
# Intent Classification
# -------------------------------
def identify_intent(text: str) -> str:
    text = text.lower()

    if "meeting" in text or "schedule" in text:
        return "schedule_meeting"
    elif "remind" in text or "reminder" in text:
        return "set_reminder"
    elif "alarm" in text or "wake me" in text:
        return "set_alarm"
    elif "task" in text or "to-do" in text or "add" in text:
        return "add_task"
    elif "note" in text or "note down" in text:
        return "take_note"
    elif "send" in text or "email" in text or "message" in text:
        return "send_message"
    elif "what is" in text or "who is" in text or "tell me" in text:
        return "get_information"
    else:
        return "unknown"


# -------------------------------
# Entity Extraction using spaCy
# -------------------------------
def extract_entities(text: str) -> dict:
    doc = nlp(text)
    entities = {}

    for ent in doc.ents:
        entities.setdefault(ent.label_, []).append(ent.text)

    return entities


# -------------------------------
# Execution Plan Generator
# -------------------------------
def generate_execution_plan(intent: str) -> list:
    plans = {
        "schedule_meeting": [
            "Extract meeting date and time",
            "Identify participants",
            "Create calendar event",
            "Confirm meeting scheduled"
        ],
        "set_reminder": [
            "Extract reminder message",
            "Extract reminder time",
            "Store reminder",
            "Trigger notification at scheduled time"
        ],
        "set_alarm": [
            "Extract alarm time",
            "Set system alarm",
            "Confirm alarm creation"
        ],
        "add_task": [
            "Extract task description",
            "Add task to task list",
            "Confirm task added"
        ],
        "take_note": [
            "Extract note content",
            "Save note",
            "Confirm note saved"
        ],
        "send_message": [
            "Extract recipient name",
            "Extract message content",
            "Send message",
            "Confirm message delivery"
        ],
        "get_information": [
            "Understand user query",
            "Retrieve relevant information",
            "Display answer to user"
        ],
        "unknown": [
            "Ask user for clarification",
            "Reprocess input"
        ]
    }
    return plans.get(intent, plans["unknown"])


# -------------------------------
# Main Assistant Logic
# -------------------------------
def run_assistant(user_input: str) -> dict:
    intent = identify_intent(user_input)
    entities = extract_entities(user_input)
    execution_plan = generate_execution_plan(intent)
    current_date = datetime.now().date().isoformat()

    output = {
        "action_identified": intent,
        "action_type": intent.replace("_", " "),
        "current_date": current_date,
        "entities": entities,
        "execution_plan": execution_plan
    }

    return output


# -------------------------------
# Program Entry Point
# -------------------------------
if __name__ == "__main__":
    print("🤖 AI Task Assistant (Single File)")
    print("--------------------------------")

    user_command = input("Enter your command: ")

    result = run_assistant(user_command)

    print("\n✅ Result:")
    for key, value in result.items():
        print(f"{key}: {value}")
