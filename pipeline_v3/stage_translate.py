"""stage_translate.py

Combined translation stage.

This file replaces the older:
  - stage_tamil_translate.py  (English -> Tamil via OpenAI)
  - stage_theni_converter.py  (Tamil -> Theni Tamil)

Dialect conversion (Tamil <-> Theni Tamil) is done locally using a LoRA fine-tuned
mBART model, following the same inference pattern as translate.py.

Folder expectations (relative to this file):
  ./stage_tamil_thenitamil_model/<something with 'best' in name>/
  ./stage_thenitamil_tamil_model/<something with 'best' in name>/

Each "best" folder can be either:
  1) A PEFT/LoRA adapter folder (adapter_config.json present), OR
  2) A fully merged HuggingFace model folder (config.json + weights).
"""

from __future__ import annotations

import gc
from pathlib import Path
from typing import Any, Dict, Optional

import torch
from transformers import MBart50Tokenizer, MBartForConditionalGeneration

try:
    # PEFT is only needed if your "best" dirs are LoRA adapter folders.
    from peft import PeftModel

    _PEFT_AVAILABLE = True
except Exception:
    PeftModel = None  # type: ignore
    _PEFT_AVAILABLE = False

from config import TRANSLATION_TEMPERATURE
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
    if not (model_dir / "config.json").is_file():
        return False
    for item in model_dir.iterdir():
        if item.is_file() and _is_hf_weight_file(item.name):
            return True
    return False


def _pick_best_model_dir(root: Path) -> Path:
    """Find a folder containing 'best' in its name.

    If multiple matches exist, the most recently modified is picked.
    """
    if not root.is_dir():
        raise FileNotFoundError(
            f"Model root folder not found: {root}\n"
            "Expected folder relative to stage_translate.py."
        )

    candidates: list[Path] = []

    # Prefer immediate children first (most common structure)
    for child in root.iterdir():
        if child.is_dir() and "best" in child.name.lower():
            candidates.append(child)

    # If nothing found, search deeper
    if not candidates:
        for child in root.rglob("*"):
            if child.is_dir() and "best" in child.name.lower():
                candidates.append(child)

    if not candidates:
        raise FileNotFoundError(
            f"No folder with 'best' found inside: {root}\n"
            "Create a subfolder whose name contains 'best' and put the model there."
        )

    # Keep only folders that look like a PEFT adapter OR a full HF model.
    filtered = [
        c
        for c in candidates
        if _looks_like_peft_adapter_dir(c) or _looks_like_full_hf_model_dir(c)
    ]
    if filtered:
        candidates = filtered

    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


class StageTranslator:
    """English -> Tamil via OpenAI, plus Tamil <-> Theni Tamil via local models."""

    def __init__(
        self,
        core: Optional[OpenAICore] = None,
        *,
        max_length: int = 128,
        num_beams: int = 5,
    ) -> None:
        self.core = core
        self.max_length = max_length
        self.num_beams = num_beams

        self.base_dir = Path(__file__).resolve().parent
        self.tamil_to_theni_root = self.base_dir / "stage_tamil_thenitamil_model"
        self.theni_to_tamil_root = self.base_dir / "stage_thenitamil_tamil_model"

        self.tamil_to_theni_dir = _pick_best_model_dir(self.tamil_to_theni_root)
        self.theni_to_tamil_dir = _pick_best_model_dir(self.theni_to_tamil_root)

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Tokenizer: try local first (in case of offline usage), else fallback to base model.
        self.tokenizer = self._load_tokenizer()

        # Lazy-loaded merged models
        self._tamil_to_theni_model: Optional[MBartForConditionalGeneration] = None
        self._theni_to_tamil_model: Optional[MBartForConditionalGeneration] = None

    def _load_tokenizer(self) -> MBart50Tokenizer:
        # Prefer a tokenizer saved in either model dir (common when exporting)
        for candidate in (self.tamil_to_theni_dir, self.theni_to_tamil_dir):
            try:
                tok = MBart50Tokenizer.from_pretrained(str(candidate), local_files_only=True)
                tok.src_lang = SRC_LANG
                tok.tgt_lang = TGT_LANG
                return tok
            except Exception:
                pass

        tok = MBart50Tokenizer.from_pretrained(BASE_MODEL_NAME)
        tok.src_lang = SRC_LANG
        tok.tgt_lang = TGT_LANG
        return tok

    def _clear_memory(self) -> None:
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def _load_local_model(self, model_dir: Path) -> MBartForConditionalGeneration:
        """Load either a PEFT adapter folder (LoRA) or a full merged HF model folder."""
        self._clear_memory()

        dtype = torch.float16 if torch.cuda.is_available() else torch.float32

        if _looks_like_peft_adapter_dir(model_dir):
            if not _PEFT_AVAILABLE:
                raise RuntimeError(
                    "Your model folder looks like a PEFT/LoRA adapter (adapter_config.json found), "
                    "but 'peft' is not installed. Install peft or export a merged model folder."
                )

            base_model = MBartForConditionalGeneration.from_pretrained(
                BASE_MODEL_NAME,
                torch_dtype=dtype,
            )
            model = PeftModel.from_pretrained(base_model, str(model_dir), local_files_only=True)  # type: ignore
            model = model.merge_and_unload()  # type: ignore
        elif _looks_like_full_hf_model_dir(model_dir):
            model = MBartForConditionalGeneration.from_pretrained(
                str(model_dir),
                torch_dtype=dtype,
                local_files_only=True,
            )
        else:
            raise FileNotFoundError(
                f"Model folder does not look like a PEFT adapter or a merged HF model: {model_dir}\n"
                "Expected adapter_config.json (PEFT) OR config.json + weight files (merged model)."
            )

        model.to(self.device)
        model.eval()
        return model

    def _ensure_tamil_to_theni_model(self) -> MBartForConditionalGeneration:
        if self._tamil_to_theni_model is None:
            self._tamil_to_theni_model = self._load_local_model(self.tamil_to_theni_dir)
        return self._tamil_to_theni_model

    def _ensure_theni_to_tamil_model(self) -> MBartForConditionalGeneration:
        if self._theni_to_tamil_model is None:
            self._theni_to_tamil_model = self._load_local_model(self.theni_to_tamil_dir)
        return self._theni_to_tamil_model

    # ---------------------------------------------------------------------
    # OpenAI translation (English -> Tamil)
    # ---------------------------------------------------------------------
    def english_to_tamil(self, english_text: str, profile: Dict[str, Any]) -> str:
        """Translate English -> Tamil using OpenAI (same logic as old stage_tamil_translate.py)."""
        if self.core is None:
            raise RuntimeError("OpenAICore was not provided. Pass OpenAICore() to StageTranslator(core=...).")

        tone = profile.get("behaviour_rules", {}).get("preferred_tone", "warm and clear")

        system_prompt = (
            "You are an expert English-to-Tamil translator. "
            "Translate into natural, modern, easy-to-read Tamil. "
            "Preserve meaning, tone, and safety. "
            "Do not over-Sanskritize. Do not transliterate English unless necessary."
        )

        user_prompt = f"""
Preferred tone:
{tone}

Translate the following English into natural Tamil.
Keep it culturally clear and easy to understand.
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

    # ---------------------------------------------------------------------
    # Local dialect conversion
    # ---------------------------------------------------------------------
    def tamil_to_thenitamil(self, tamil_text: str) -> str:
        """Convert standard Tamil -> Theni Tamil using the local LoRA model."""
        model = self._ensure_tamil_to_theni_model()
        return self._generate(tamil_text, model)

    def thenitamil_to_tamil(self, theni_tamil_text: str) -> str:
        """Convert Theni Tamil -> standard Tamil using the local LoRA model."""
        model = self._ensure_theni_to_tamil_model()
        return self._generate(theni_tamil_text, model)

    def _generate(self, text: str, model: MBartForConditionalGeneration) -> str:
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

        return self.tokenizer.decode(output_ids[0], skip_special_tokens=True)