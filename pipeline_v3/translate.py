"""
Local mBART + LoRA inference helper.

- Can be used as a standalone script (interactive demo).
- Or imported as a module by stage_translate.py.

Expected adapter folder format:
  <adapter_dir>/
    adapter_config.json
    adapter_model.safetensors (or .bin)
    ... etc

If you have a parent folder containing multiple checkpoints, you can use:
  find_best_model_subdir(<parent>) -> picks directory containing "best" in name.
"""

from __future__ import annotations

import gc
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import torch
from peft import PeftModel
from transformers import MBart50Tokenizer, MBartForConditionalGeneration


def _select_device() -> torch.device:
    if torch.cuda.is_available():
        device = torch.device("cuda")
        print(f"✓ Using GPU: {torch.cuda.get_device_name(0)}")
    else:
        device = torch.device("cpu")
        print("⚠ No GPU found — using CPU (this will be slower)")
    return device


def find_best_model_subdir(parent_dir: Path) -> Path:
    """
    Given a folder that contains multiple model dirs, pick the one with 'best' in the name.
    If multiple matches, picks the most recently modified.
    If no subdirs match, but parent_dir itself looks like a model dir, return parent_dir.
    """
    parent_dir = Path(parent_dir).resolve()

    if not parent_dir.exists() or not parent_dir.is_dir():
        raise FileNotFoundError(f"Model parent directory not found: {parent_dir}")

    # Candidate subdirectories
    subdirs = [p for p in parent_dir.iterdir() if p.is_dir()]
    best_matches = [p for p in subdirs if "best" in p.name.lower()]

    def mtime(p: Path) -> float:
        try:
            return p.stat().st_mtime
        except Exception:
            return 0.0

    if best_matches:
        best_matches.sort(key=mtime, reverse=True)
        return best_matches[0]

    # If no 'best' folder, maybe parent itself is the adapter folder
    # quick heuristic: adapter_config.json exists
    if (parent_dir / "adapter_config.json").exists():
        return parent_dir

    # Otherwise fall back to most recently modified subdir (if any)
    if subdirs:
        subdirs.sort(key=mtime, reverse=True)
        return subdirs[0]

    raise FileNotFoundError(
        f"No model folders found under: {parent_dir} (and parent is not an adapter dir)"
    )


@dataclass
class LocalMbartLoraTranslator:
    model_dir: Path
    base_model_name: str = "facebook/mbart-large-50"
    src_lang: str = "ta_IN"
    tgt_lang: str = "ta_IN"
    max_length: int = 128

    _tokenizer: Optional[MBart50Tokenizer] = None
    _model: Optional[MBartForConditionalGeneration] = None
    _device: Optional[torch.device] = None

    def __post_init__(self) -> None:
        self.model_dir = Path(self.model_dir).resolve()

    @property
    def device(self) -> torch.device:
        if self._device is None:
            self._device = _select_device()
        return self._device

    def load(self) -> None:
        """Load tokenizer + base model + LoRA adapter, merge, and keep in memory."""
        if self._tokenizer is not None and self._model is not None:
            return

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        if not self.model_dir.is_dir():
            raise FileNotFoundError(f"Model directory not found: {self.model_dir}")

        print(f"\n🔄 Loading tokenizer... ({self.base_model_name})")
        tokenizer = MBart50Tokenizer.from_pretrained(self.base_model_name)
        tokenizer.src_lang = self.src_lang
        tokenizer.tgt_lang = self.tgt_lang

        print("🔄 Loading base mBART model...")
        dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        base_model = MBartForConditionalGeneration.from_pretrained(
            self.base_model_name,
            torch_dtype=dtype,
        )

        print(f"🔄 Loading LoRA adapter from: {self.model_dir}")
        model = PeftModel.from_pretrained(base_model, str(self.model_dir), local_files_only=True)

        print("🔄 Merging LoRA into base model...")
        model = model.merge_and_unload()
        model.to(self.device)
        model.eval()

        self._tokenizer = tokenizer
        self._model = model
        print("✓ Local model loaded successfully!\n")

    def translate(self, text: str) -> str:
        """Run inference."""
        if not text.strip():
            return ""

        self.load()
        assert self._tokenizer is not None
        assert self._model is not None

        self._tokenizer.src_lang = self.src_lang

        inputs = self._tokenizer(
            text,
            return_tensors="pt",
            max_length=self.max_length,
            truncation=True,
        ).to(self.device)

        forced_bos_token_id = self._tokenizer.lang_code_to_id[self.tgt_lang]

        with torch.no_grad():
            output_ids = self._model.generate(
                **inputs,
                forced_bos_token_id=forced_bos_token_id,
                num_beams=5,
                max_length=self.max_length,
                early_stopping=True,
            )

        return self._tokenizer.decode(output_ids[0], skip_special_tokens=True)


# -----------------------------------------------------------------------------
# Standalone demo mode (kept for convenience)
# -----------------------------------------------------------------------------
def main() -> None:
    """
    Demo expects a local folder named 'best_model' next to this file, matching your old layout.
    If you want to use the newer multi-folder layout, use StageTranslator instead.
    """
    here = Path(__file__).resolve().parent
    default_model_dir = here / "best_model"

    if not default_model_dir.exists():
        print(f"\n✗ Default demo model directory not found: {default_model_dir}")
        print("  If you're using the new pipeline layout, run via main_pipeline.py instead.")
        print("  Or create 'best_model' folder next to translate.py for this demo.\n")
        raise FileNotFoundError(str(default_model_dir))

    translator = LocalMbartLoraTranslator(model_dir=default_model_dir)

    test_sentences = [
        "நீங்கள் எப்படி இருக்கிறீர்கள்",
        "இன்று மழை பெய்கிறது",
        "நான் சாப்பிட போகிறேன்",
        "அவர் வீட்டிற்கு வருகிறார்",
    ]

    print("=" * 60)
    print("  TEST TRANSLATIONS (Tamil -> Dialect using best_model)")
    print("=" * 60)
    for sentence in test_sentences:
        result = translator.translate(sentence)
        print(f"  Input  : {sentence}")
        print(f"  Output : {result}")
        print("-" * 60)

    print("\n📝 Interactive Mode — Type a Tamil sentence (type 'quit' to exit)\n")
    while True:
        try:
            text = input("Tamil ➜ ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if text.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        if text:
            result = translator.translate(text)
            print(f"Output ➜ {result}\n")


if __name__ == "__main__":
    main()