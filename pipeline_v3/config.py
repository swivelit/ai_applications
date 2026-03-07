import os
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PROFILES_DIR = DATA_DIR / "profiles"
LOGS_DIR = DATA_DIR / "logs"
CACHE_DIR = DATA_DIR / "cache"
MODELS_DIR = BASE_DIR / "models"


def _ensure_dirs(paths: Iterable[Path]) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


_ensure_dirs((DATA_DIR, PROFILES_DIR, LOGS_DIR, CACHE_DIR))


# ---------------------------------------------------------------------
# Typed env readers
# ---------------------------------------------------------------------
def _env_str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except Exception:
        return default


# ---------------------------------------------------------------------
# Core app settings
# ---------------------------------------------------------------------
OPENAI_API_KEY = _env_str("OPENAI_API_KEY", "")
OPENAI_MODEL = _env_str("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_TIMEOUT = _env_int("OPENAI_TIMEOUT", 60)
OPENAI_MAX_RETRIES = _env_int("OPENAI_MAX_RETRIES", 3)
OPENAI_CACHE_SIZE = _env_int("OPENAI_CACHE_SIZE", 128)
OPENAI_BACKOFF_BASE_SECONDS = _env_float("OPENAI_BACKOFF_BASE_SECONDS", 1.0)

APP_NAME = _env_str("APP_NAME", "persona_tamil_pipeline")
DEFAULT_USER_ID = _env_str("DEFAULT_USER_ID", "demo_user")
DEFAULT_SINGLE_PROMPT = _env_str("DEFAULT_SINGLE_PROMPT", "")
DEBUG = _env_bool("DEBUG", False)
LOG_LEVEL = _env_str("LOG_LEVEL", "INFO")

RAW_TEMPERATURE = _env_float("RAW_TEMPERATURE", 0.35)
REMODEL_TEMPERATURE = _env_float("REMODEL_TEMPERATURE", 0.45)
TRANSLATION_TEMPERATURE = _env_float("TRANSLATION_TEMPERATURE", 0.15)
THENI_TEMPERATURE = _env_float("THENI_TEMPERATURE", 0.15)

PROFILE_VERSION = _env_str("PROFILE_VERSION", "v2")
QUESTION_COUNT = _env_int("QUESTION_COUNT", 15)
MAX_HISTORY_DOCS = _env_int("MAX_HISTORY_DOCS", 8)
MAX_PROFILE_MEMORY_ROWS = _env_int("MAX_PROFILE_MEMORY_ROWS", 50)

DIRECT_MATCH_STRONG_THRESHOLD = _env_float("DIRECT_MATCH_STRONG_THRESHOLD", 0.90)
DIRECT_MATCH_SEMANTIC_THRESHOLD = _env_float("DIRECT_MATCH_SEMANTIC_THRESHOLD", 0.84)
DIRECT_MATCH_WEAK_THRESHOLD = _env_float("DIRECT_MATCH_WEAK_THRESHOLD", 0.76)

ENABLE_STAGE_FALLBACKS = _env_bool("ENABLE_STAGE_FALLBACKS", True)
ENABLE_PIPELINE_CACHE = _env_bool("ENABLE_PIPELINE_CACHE", True)
PIPELINE_CACHE_SIZE = _env_int("PIPELINE_CACHE_SIZE", 64)

TAMIL_TO_THENI_MODEL_ROOT = Path(
    _env_str("TAMIL_TO_THENI_MODEL_ROOT", str(BASE_DIR / "stage_tamil_thenitamil_model"))
)
THENI_TO_TAMIL_MODEL_ROOT = Path(
    _env_str("THENI_TO_TAMIL_MODEL_ROOT", str(BASE_DIR / "stage_thenitamil_tamil_model"))
)
TRANSLATION_MAX_CHUNK_CHARS = _env_int("TRANSLATION_MAX_CHUNK_CHARS", 700)
DIALECT_MODEL_MAX_LENGTH = _env_int("DIALECT_MODEL_MAX_LENGTH", 160)
DIALECT_MODEL_NUM_BEAMS = _env_int("DIALECT_MODEL_NUM_BEAMS", 5)

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
    "avoid definitive medical instructions. Give cautious lifestyle guidance and suggest a clinician "
    "for diagnosis, medication, or emergency concerns."
)

HEALTH_RISK_KEYWORDS = {
    "pregnant",
    "pregnancy",
    "postpartum",
    "breastfeeding",
    "conceive",
    "fertility",
    "diabetes",
    "sugar",
    "bp",
    "blood pressure",
    "heart",
    "allergy",
    "kidney",
    "medicine",
    "tablet",
    "dose",
    "dosage",
    "emergency",
    "chest pain",
    "fainting",
}