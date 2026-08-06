# Conductor fine-tuning pipeline

Adapts Mistral-7B to the four-agent orchestration roles using LoRA/QLoRA with
4-bit (NF4) quantization. Full rationale in `docs/09-fine-tuning.md`; the ~40%
inference-cost reduction vs. the chat-optimized baseline is defended there.

## Layout

- `src/dataset.py` — raw → instruction dataset, chat-template formatting
- `src/train_qlora.py` — QLoRA/LoRA training entrypoint (HF + PEFT + TRL)
- `src/eval.py` — held-out eval, accuracy/faithfulness/fluency scoring
- `src/export_merged.py` — merge adapters and push to the registry
- `src/serve_vllm.py` — one-shot vLLM serving + OpenAI-compatible endpoint

## Usage

```bash
cd finetune
uv sync
python -m src.dataset --raw ./data --out ./data/processed
python -m src.train_qlora --config configs/qlora.yaml
python -m src.eval --adapters ./out/lora --split val
python -m src.export_merged
vllm serve --config configs/vllm.yaml
```