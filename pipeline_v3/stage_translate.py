from __future__ import annotations

import gc
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import torch
from transformers import MBart50Tokenizer, MBartForConditionalGeneration

try:
    from peft import PeftModel

    _PEFT_AVAILABLE = True
except Exception:
    PeftModel = None  # type: ignore
    _PEFT_AVAILABLE = False

from config import (
    DIALECT_MODEL_MAX_LENGTH,
    DIALECT_MODEL_NUM_BEAMS,
    ENABLE_STAGE_FALLBACKS,
    ENABLE_TAMIL_VALIDATION,
    ENABLE_TRANSLATION_REFINEMENT,
    MIN_TAMIL_CHAR_RATIO,
    TAMIL_TO_THENI_MODEL_ROOT,
    THENI_TO_TAMIL_MODEL_ROOT,
    TRANSLATION_MAX_CHUNK_CHARS,
    TRANSLATION_RETRY_ON_NON_TAMIL,
    TRANSLATION_TEMPERATURE,
)
from stage_openai_core import OpenAICore


BASE_MODEL_NAME = "facebook/mbart-large-50"
SRC_LANG = "ta_IN"
TGT_LANG = "ta_IN"


def _is_hf_weight_file(filename: str) -> bool:
    lower = filename.lower()
    return (
        lower.endswith(".bin")
        or lower.endswith(".safetensors")
        or "pytorch_model" in lower
        or "model" in lower
    )


def _looks_like_peft_adapter_dir(model_dir: Path) -> bool:
    return (model_dir / "adapter_config.json").is_file()


def _looks_like_full_hf_model_dir(model_dir: Path) -> bool:
    if not model_dir.is_dir() or not (model_dir / "config.json").is_file():
        return False
    for item in model_dir.iterdir():
        if item.is_file() and _is_hf_weight_file(item.name):
            return True
    return False


def _pick_best_model_dir(root: Path) -> Optional[Path]:
    if not root.is_dir():
        return None

    candidates: List[Path] = []
    for child in root.iterdir():
        if child.is_dir() and "best" in child.name.lower():
            candidates.append(child)

    if not candidates:
        for child in root.rglob("*"):
            if child.is_dir() and "best" in child.name.lower():
                candidates.append(child)

    filtered = [
        candidate
        for candidate in candidates
        if _looks_like_peft_adapter_dir(candidate) or _looks_like_full_hf_model_dir(candidate)
    ]
    if filtered:
        candidates = filtered

    if not candidates:
        return None

    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


class StageTranslator:
    def __init__(
        self,
        core: Optional[OpenAICore] = None,
        *,
        max_length: int = DIALECT_MODEL_MAX_LENGTH,
        num_beams: int = DIALECT_MODEL_NUM_BEAMS,
    ) -> None:
        self.core = core
        self.max_length = max_length
        self.num_beams = num_beams

        self.tamil_to_theni_root = TAMIL_TO_THENI_MODEL_ROOT
        self.theni_to_tamil_root = THENI_TO_TAMIL_MODEL_ROOT

        self.tamil_to_theni_dir = _pick_best_model_dir(self.tamil_to_theni_root)
        self.theni_to_tamil_dir = _pick_best_model_dir(self.theni_to_tamil_root)

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer: Optional[MBart50Tokenizer] = self._load_tokenizer_if_available()

        self._tamil_to_theni_model: Optional[MBartForConditionalGeneration] = None
        self._theni_to_tamil_model: Optional[MBartForConditionalGeneration] = None

    @staticmethod
    def _contains_tamil(text: str) -> bool:
        return bool(re.search(r"[\u0B80-\u0BFF]", str(text or "")))

    @staticmethod
    def _cleanup_tamil(text: str) -> str:
        text = str(text or "").strip()
        text = re.sub(r"\s+([,.;:!?])", r"\1", text)
        text = re.sub(r"\s{2,}", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def _split_into_chunks(text: str, chunk_size: int = TRANSLATION_MAX_CHUNK_CHARS) -> List[str]:
        text = str(text or "").strip()
        if len(text) <= chunk_size:
            return [text] if text else []

        parts = re.split(r"(?<=[.!?\n])\s+", text)
        chunks: List[str] = []
        current = ""
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if len(current) + len(part) + 1 <= chunk_size:
                current = f"{current} {part}".strip()
            else:
                if current:
                    chunks.append(current)
                if len(part) <= chunk_size:
                    current = part
                else:
                    for i in range(0, len(part), chunk_size):
                        chunks.append(part[i : i + chunk_size].strip())
                    current = ""
        if current:
            chunks.append(current)
        return chunks

    @staticmethod
    def _tamil_char_ratio(text: str) -> float:
        text = str(text or "")
        if not text:
            return 0.0
        tamil_chars = sum(1 for ch in text if "\u0B80" <= ch <= "\u0BFF")
        alpha_num_chars = sum(1 for ch in text if ch.isalnum()) or len(text)
        return tamil_chars / max(alpha_num_chars, 1)

    def _looks_like_valid_tamil_output(self, text: str) -> bool:
        if not ENABLE_TAMIL_VALIDATION:
            return True
        return self._contains_tamil(text) and self._tamil_char_ratio(text) >= MIN_TAMIL_CHAR_RATIO

    def _load_tokenizer_if_available(self) -> Optional[MBart50Tokenizer]:
        for candidate in (self.tamil_to_theni_dir, self.theni_to_tamil_dir):
            if candidate is None:
                continue
            try:
                tokenizer = MBart50Tokenizer.from_pretrained(str(candidate), local_files_only=True)
                tokenizer.src_lang = SRC_LANG
                tokenizer.tgt_lang = TGT_LANG
                return tokenizer
            except Exception:
                continue

        try:
            tokenizer = MBart50Tokenizer.from_pretrained(BASE_MODEL_NAME)
            tokenizer.src_lang = SRC_LANG
            tokenizer.tgt_lang = TGT_LANG
            return tokenizer
        except Exception:
            return None

    def _clear_memory(self) -> None:
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def _load_local_model(self, model_dir: Path) -> MBartForConditionalGeneration:
        self._clear_memory()
        dtype = torch.float16 if torch.cuda.is_available() else torch.float32

        if _looks_like_peft_adapter_dir(model_dir):
            if not _PEFT_AVAILABLE:
                raise RuntimeError("PEFT model found but 'peft' is not installed.")
            base_model = MBartForConditionalGeneration.from_pretrained(BASE_MODEL_NAME, torch_dtype=dtype)
            model = PeftModel.from_pretrained(base_model, str(model_dir), local_files_only=True)  # type: ignore
            model = model.merge_and_unload()  # type: ignore
        elif _looks_like_full_hf_model_dir(model_dir):
            model = MBartForConditionalGeneration.from_pretrained(
                str(model_dir),
                torch_dtype=dtype,
                local_files_only=True,
            )
        else:
            raise FileNotFoundError(f"Model folder is invalid or incomplete: {model_dir}")

        model.to(self.device)
        model.eval()
        return model

    def _ensure_tamil_to_theni_model(self) -> Optional[MBartForConditionalGeneration]:
        if self.tamil_to_theni_dir is None:
            return None
        if self._tamil_to_theni_model is None:
            self._tamil_to_theni_model = self._load_local_model(self.tamil_to_theni_dir)
        return self._tamil_to_theni_model

    def _translate_chunk(self, english_text: str, tone: str, answer_length: str) -> str:
        if self.core is None:
            raise RuntimeError("OpenAICore was not provided.")

        system_prompt = (
            "You are an expert English-to-Tamil translator. Translate into natural, modern, easy-to-read Tamil. "
            "Preserve meaning, tone, safety, and answer structure. Do not over-Sanskritize. "
            "Do not transliterate English unless necessary."
        )
        user_prompt = f"""
Preferred tone:
{tone}

Preferred answer length feel:
{answer_length}

Translate the following English into natural Tamil.
Keep it culturally clear and easy to understand.
Preserve headings, lists, and practical structure.
Output only Tamil text.

English text:
{english_text}
""".strip()
        return self.core.generate_text(
            system_prompt,
            user_prompt,
            temperature=TRANSLATION_TEMPERATURE,
            max_output_tokens=1200,
        )

    def _retry_translate_chunk(self, english_text: str) -> str:
        if self.core is None:
            return english_text
        system_prompt = (
            "Translate English into pure Tamil script as much as naturally possible. "
            "Return only Tamil text, keeping the meaning unchanged."
        )
        user_prompt = f"Translate this into Tamil only:\n\n{english_text}"
        return self.core.generate_text(
            system_prompt,
            user_prompt,
            temperature=0.05,
            max_output_tokens=1200,
        )

    def _refine_combined_tamil(self, tamil_text: str, tone: str, answer_length: str) -> str:
        if self.core is None or not tamil_text:
            return tamil_text
        system_prompt = (
            "You are a Tamil editor. Improve fluency, readability, and consistency without changing the meaning. "
            "Preserve headings, lists, and safety wording."
        )
        user_prompt = f"""
Target tone:
{tone}

Target answer-length feel:
{answer_length}

Polish the Tamil below while preserving the exact meaning.
Output only Tamil text.

Tamil text:
{tamil_text}
""".strip()
        return self.core.generate_text(
            system_prompt,
            user_prompt,
            temperature=0.08,
            max_output_tokens=1400,
        )

    def english_to_tamil_with_meta(self, english_text: str, profile: Dict[str, Any]) -> Dict[str, Any]:
        cleaned_english = str(english_text or "").strip()
        if not cleaned_english:
            return {
                "tamil_text": "",
                "source": "empty",
                "chunk_count": 0,
                "refinement_applied": False,
                "validation_passed": True,
            }

        if self._contains_tamil(cleaned_english):
            cleaned = self._cleanup_tamil(cleaned_english)
            return {
                "tamil_text": cleaned,
                "source": "passthrough",
                "chunk_count": 1,
                "refinement_applied": False,
                "validation_passed": self._looks_like_valid_tamil_output(cleaned),
            }

        rules = profile.get("behaviour_rules", {}) or {}
        tone = rules.get("preferred_tone", "warm and clear")
        answer_length = rules.get("preferred_answer_length", "1-2 balanced paragraphs")
        chunks = self._split_into_chunks(cleaned_english)
        outputs: List[str] = []

        for chunk in chunks:
            translated = self._cleanup_tamil(self._translate_chunk(chunk, tone=tone, answer_length=answer_length))
            if TRANSLATION_RETRY_ON_NON_TAMIL and not self._looks_like_valid_tamil_output(translated):
                retry_text = self._cleanup_tamil(self._retry_translate_chunk(chunk))
                if self._looks_like_valid_tamil_output(retry_text):
                    translated = retry_text
            outputs.append(translated)

        combined = self._cleanup_tamil("\n\n".join(outputs))
        refinement_applied = False

        if ENABLE_TRANSLATION_REFINEMENT and (len(chunks) > 1 or not self._looks_like_valid_tamil_output(combined)):
            refined = self._cleanup_tamil(self._refine_combined_tamil(combined, tone=tone, answer_length=answer_length))
            if refined:
                combined = refined
                refinement_applied = True

        return {
            "tamil_text": combined,
            "source": "openai",
            "chunk_count": len(chunks),
            "refinement_applied": refinement_applied,
            "validation_passed": self._looks_like_valid_tamil_output(combined),
        }

    def english_to_tamil(self, english_text: str, profile: Dict[str, Any]) -> str:
        return str(self.english_to_tamil_with_meta(english_text, profile).get("tamil_text", "")).strip()

    def tamil_to_thenitamil(self, tamil_text: str) -> str:
        tamil_text = self._cleanup_tamil(tamil_text)
        if not tamil_text:
            return tamil_text

        model = self._ensure_tamil_to_theni_model()
        if model is None or self.tokenizer is None:
            return tamil_text if ENABLE_STAGE_FALLBACKS else self._raise_missing_model("Tamil -> Theni Tamil")

        chunks = self._split_into_chunks(tamil_text)
        converted = [self._generate(chunk, model) for chunk in chunks]
        return self._cleanup_tamil("\n\n".join(converted))

    @staticmethod
    def _raise_missing_model(direction: str) -> str:
        raise FileNotFoundError(f"Local dialect model unavailable for {direction} conversion.")

    def _generate(self, text: str, model: MBartForConditionalGeneration) -> str:
        if not text or self.tokenizer is None:
            return text

        self.tokenizer.src_lang = SRC_LANG
        self.tokenizer.tgt_lang = TGT_LANG

        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            max_length=self.max_length,
            truncation=True,
        ).to(self.device)

        forced_bos_token_id = self.tokenizer.lang_code_to_id[TGT_LANG]

        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                forced_bos_token_id=forced_bos_token_id,
                num_beams=self.num_beams,
                max_length=self.max_length,
                early_stopping=True,
            )

        return self._cleanup_tamil(self.tokenizer.decode(output_ids[0], skip_special_tokens=True))