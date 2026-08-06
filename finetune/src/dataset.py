"""Dataset construction for Conductor agent fine-tuning.

Raw records (per-agent transcripts logged by the orchestrator, plus synthetic
seeds) are cleaned, deduplicated, and formatted with the target chat template
into flat prompt → completion pairs, then split train/validation.

Output rows:
    {"messages": [{"role": "...", "content": "..."}], "agent": "planner", "metadata": {}}
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

AGENTS = ("planner", "researcher", "executor", "critic", "finalizer")

_INSTRUCTION_MARKERS = ("\nAnswer:", "\n### Response:", "\n[INST]", "### Instruction:")


def parse_example(raw: dict, agent: str) -> dict | None:
    """Normalize one raw transcript/QA line into an instruction example."""
    instruction = raw.get("instruction") or raw.get("query") or raw.get("prompt")
    response = raw.get("response") or raw.get("answer") or raw.get("completion")
    if not instruction or not response:
        return None
    messages = [
        *({"role": "system", "content": raw["system"]} if raw.get("system") else []),
        {"role": "user", "content": str(instruction)},
        {"role": "assistant", "content": str(response)},
    ]
    return {"messages": messages, "agent": agent, "metadata": {"source": raw.get("source", "synthetic")}}


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text


def dedupe(examples: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for ex in examples:
        key = ex["messages"][-1]["content"]
        if key not in seen:
            seen.add(key)
            out.append(ex)
    return out


def build_dataset(raw_dir: Path, out_dir: Path, train_split: float = 0.95, seed: int = 42) -> tuple[int, int]:
    random.seed(seed)
    examples: list[dict] = []
    for file in sorted(raw_dir.glob("*.jsonl")):
        with file.open() as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                raw = json.loads(line)
                agent = raw.get("agent", "planner")
                if agent not in AGENTS:
                    continue
                example = parse_example(raw, agent)
                if example:
                    examples.append(example)

    examples = deduard(examples)
    random.shuffle(examples)
    split = int(len(examples) * train_split)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out_dir / "train.jsonl", examples[:split])
    _write_jsonl(out_dir / "val.jsonl", examples[split:])
    return len(examples[:split]), len(examples[split:])


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=Path("./data/raw"))
    parser.add_argument("--out", type=Path, default=Path("./data/processed"))
    parser.add_argument("--train-split", type=float, default=0.95)
    args = parser.parse_args()
    train, val = build_dataset(args.raw, args.out, args.train_split)
    print(json.dumps({"train": train, "val": val}))


if __name__ == "__main__":
    main()