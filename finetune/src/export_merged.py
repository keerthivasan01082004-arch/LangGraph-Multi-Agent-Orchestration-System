"""Merge LoRA adapters into the base model and export to the model registry.

vLLM loads the merged weights directly (no PEFT runtime in serving). The
artifact is pushed to a private HF repo or S3 and referenced by env
MODEL_ID in the backend (docs/09-fine-tuning.md).
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Literal

from train_qlora import TrainConfig


def merge_and_save(cfg: TrainConfig, adapters_dir: Path, save_dir: Path) -> None:
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    base = AutoModelForCausalLM.from_pretrained(cfg.base_model, device_map="cpu", torch_dtype="auto")
    model = PeftModel.from_pretrained(base, adapters_dir)
    model = model.merge_and_unload()

    save_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(save_dir)
    tokenizer = AutoTokenizer.from_pretrained(adapters_dir)
    tokenizer.save_pretrained(save_dir)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=Path("configs/qlora.yaml"))
    ap.add_argument("--adapters", type=Path, default=Path("./out/lora"))
    ap.add_argument("--save", type=Path, default=Path("./out/merged"))
    args = ap.parse_args()
    cfg = TrainConfig.from_yaml(args.config)
    merge_and_save(cfg, args.adapters, args.save)
    print(f"merged weights -> {args.save}")


if __name__ == "__main__":
    main()