import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PROFILES_DIR = DATA_DIR / "profiles"
LOGS_DIR = DATA_DIR / "logs"

for directory in (DATA_DIR, PROFILES_DIR, LOGS_DIR):
    directory.mkdir(parents=True, exist_ok=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is missing. Add it to .env")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_TIMEOUT = int(os.getenv("OPENAI_TIMEOUT", "60"))
OPENAI_MAX_RETRIES = int(os.getenv("OPENAI_MAX_RETRIES", "3"))
APP_NAME = os.getenv("APP_NAME", "persona_tamil_pipeline")
DEFAULT_USER_ID = os.getenv("DEFAULT_USER_ID", "demo_user")
DEBUG = os.getenv("DEBUG", "false").strip().lower() == "true"

RAW_TEMPERATURE = float(os.getenv("RAW_TEMPERATURE", "0.4"))
REMODEL_TEMPERATURE = float(os.getenv("REMODEL_TEMPERATURE", "0.5"))
TRANSLATION_TEMPERATURE = float(os.getenv("TRANSLATION_TEMPERATURE", "0.2"))
THENI_TEMPERATURE = float(os.getenv("THENI_TEMPERATURE", "0.3"))

PROFILE_VERSION = "v1"
QUESTION_COUNT = 15

PREGNANCY_CUSTOM_AVOID_LIST = [
    "pineapple",
    "alcohol",
    "smoking",
    "tobacco",
    "unprescribed medicine",
    "crash dieting",
]

MEDICAL_SAFETY_NOTE = (
    "For pregnancy, diabetes, blood pressure, allergies, kidney issues, or other health conditions, "
    "avoid definitive medical instructions. Give cautious lifestyle guidance and suggest a clinician for diagnosis, medication, or emergency concerns."
)