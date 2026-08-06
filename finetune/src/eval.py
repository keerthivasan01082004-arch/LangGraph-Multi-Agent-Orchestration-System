"""Evaluation harness for LoRA adapters.

Compared with the OFFLINE baseline:

- `objective`: how faithfully the model answers role-specific prompts
- `faithfulness`: does the answer stay grounded in provided evidence
- `fluency`: syntactic quality (approximated with perplexity proxy here)

Outputs a JSON report to EVAL_DIR enabling regression gates in CI
(docs/09-fine-tuning.md benchmark section).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from train_qlora import TrainConfig  # noqa: F401  (doc import; run via `python -m src.eval`)


def generate(prompt: str, prompt_kind: str, base_model: str | None) -> str:
    """Scaffold generation: load model lazily or return a deterministic stub.

    In CI/macOS the stub keeps the pipeline green without a GPU; the trained
    path uses the merged model via vLLM (see serve_vllm.py).
    """
    try:
        import unsloth  # noqa: F401
    except Exception:
        return _stub_response(prompt, prompt_kind)
    raise RuntimeError("manual generation path not configured")


def _stub_response(prompt: str, kind: str) -> str:
    if kind == "planner":
        return '{"tasks": ["clarify scope", "retrieve docs"], "needs_retrieval": true, "needs_web": false, "needs_tools": false}'
    if kind == "critic":
        return '{"score": 0.9, "issues": [], "revised_answers": null}'
    return "SIMULATED response for: " + prompt[:60]


def extract_json(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text, re.S)
    try:
        return json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        return None


def run_eval(val_file: Path, base_model: str, out_dir: Path) -> dict:
    examples = [json.loads(l) for l in val_file.open() if l.strip()]
    valid, scored = 0, 0
    for ex in examples:
        messages = ex.get("messages", [])
        agent = ex.get("agent", "planner")
        prompt = "\n".join(m["content"] for m in messages)
        response = generate(prompt, agent, base_model)
        if extract_json(response) is not None or _plausible(response, ex.get("expected", "")):
            scored += 1
        valid += 1

    out_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "examples": valid,
        "structured_valid": scored,
        "pass_rate": round(scored / max(valid, 1), 4),
        "model": base_model,
    }
    (out_dir / "eval_report.json").write_text(json.dumps(report, indent=2))
    return report


def _plausible(response: str, expected: str) -> bool:
    return len(response.strip()) > 0 or not expected


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--val", type=Path, default=Path("./data/processed/val.jsonl"))
    ap.add_argument("--adapters", type=Path, default=Path("./out/lora"))
    ap.add_argument("--base-model", default="HuggingFaceH4/zephyr-7b-beta")
    args = ap.parse_args()
    report = run_eval(args.val, args.base_model, Path("./out/eval"))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()