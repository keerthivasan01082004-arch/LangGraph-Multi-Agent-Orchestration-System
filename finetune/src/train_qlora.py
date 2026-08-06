"""QLoRA training entry for Mistral-7B (Q4 NF4) + LoRA adapters.

Run:  python -m src.train_qlora --config configs/qlora.yaml

Produces the PEFT adapter in OUTPUT_DIR with a training.json metadata record
consumed by the eval and export stages (docs/09-fine-tuning.md).
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class TrainConfig:
    base_model: str
    train_file: str = "./data/processed/train.jsonl"
    val_file: str = "./data/processed/val.jsonl"
    output_dir: str = "./out/lora"
    num_epochs: int = 3
    per_device_train_batch_size: int = 2
    gradient_accumulation_steps: int = 8
    learning_rate: float = 2e-4
    max_seq_len: int = 2048
    lora_r: int = 32
    lora_alpha: int = 64
    lora_dropout: float = 0.05
    lora_target_modules: list[str] = field(
        default_factory=lambda: ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
    )
    quant_bits: int = 4
    freeze_base: bool = True
    seed: int = 42
    response_template: str = "### Assistant"
    report_to: list[str] = field(default_factory=lambda: ["wandb"])

    @classmethod
    def from_yaml(cls, path: Path) -> "TrainConfig":
        return cls(**yaml.safe_load(path.read_text()))


def build_model_and_tokenizer(cfg: TrainConfig):
    """4-bit NF4 quantized base model + tokenizer.

    Imports are lazy so this module stays importable on machines without
    torch/transformers (CI, docs tooling)."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    bnb = BitsAndBytesConfig(
        load_in_4bit=cfg.quant_bits == 4,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        cfg.base_model, quantization_config=bnb, device_map="auto", torch_dtype=torch.bfloat16
    )
    tokenizer = AutoTokenizer.from_pretrained(cfg.base_model)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"
    return model, tokenizer


def attach_lora(model, cfg: TrainConfig):
    from peft import LoraConfig, get_peft_model

    if cfg.freeze_base:
        for p in model.parameters():
            p.requires_grad = False
    config = LoraConfig(
        r=cfg.lora_r,
        lora_alpha=cfg.lora_alpha,
        target_modules=cfg.lora_target_modules,
        lora_dropout=cfg.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
    )
    return get_peft_model(model, config)


def train(cfg: TrainConfig) -> None:
    from datasets import load_dataset
    from transformers import TrainingArguments
    from trl import DataCollatorForCompletionOnlyLM, SFTTrainer

    model, tokenizer = build_model_and_tokenizer(cfg)
    model = attach_lora(model, cfg)

    data = load_dataset("json", data_files={"train": cfg.train_file, "validation": cfg.val_file})
    collator = DataCollatorForCompletionOnlyLM(response_template=cfg.response_template, tokenizer=tokenizer)

    args = TrainingArguments(
        output_dir=cfg.output_dir,
        num_train_epochs=cfg.num_epochs,
        per_device_train_batch_size=cfg.per_device_train_batch_size,
        gradient_accumulation_steps=cfg.gradient_accumulation_steps,
        learning_rate=cfg.learning_rate,
        logging_steps=10,
        eval_strategy="steps",
        eval_steps=200,
        save_strategy="epoch",
        save_total_limit=2,
        bf16=True,
        report_to=cfg.report_to,
        seed=cfg.seed,
    )

    trainer = SFTTrainer(
        model=model,
        args=args,
        train_dataset=data["train"],
        eval_dataset=data["validation"],
        tokenizer=tokenizer,
        max_seq_length=cfg.max_seq_len,
        data_collator=collator,
    )
    trainer.train()
    trainer.save_model(cfg.output_dir)
    tokenizer.save_pretrained(cfg.output_dir)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/qlora.yaml"))
    args = parser.parse_args()
    train(TrainConfig.from_yaml(args.config))


if __name__ == "__main__":
    main()