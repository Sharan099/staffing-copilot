"""Memory Recall Accuracy and Memory Precision."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
_SRC = PROJECT_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from eval.shared.base_evaluator import evaluate_suite


def _compute(df: pd.DataFrame):
    memory_runs = df[df["category"] == "memory"]
    if memory_runs.empty:
        memory_runs = df

    recall_vals = []
    precision_vals = []

    for _, row in memory_runs.iterrows():
        mem = row.get("agent_output", {}).get("memory") or {}
        if mem.get("recall_correct") is not None:
            recall_vals.append(1.0 if mem["recall_correct"] else 0.0)
            precision_vals.append(1.0 if mem.get("recalled_items") else 0.0)
            continue
        recalled = set(mem.get("recalled_items") or [])
        relevant = set(mem.get("relevant_items") or [])
        if not mem.get("used"):
            recall_vals.append(1.0)
            precision_vals.append(1.0)
            continue
        recall_vals.append(len(recalled & relevant) / len(relevant) if relevant else 1.0)
        precision_vals.append(len(recalled & relevant) / len(recalled) if recalled else 0.0)

    recall = sum(recall_vals) / len(recall_vals) if recall_vals else 0.0
    precision = sum(precision_vals) / len(precision_vals) if precision_vals else 0.0
    score = (recall + precision) / 2 * 100
    passed = score >= 90 and recall >= 0.9
    reason = f"Memory recall {recall:.1%}, precision {precision:.1%} ({len(memory_runs)} memory runs)."
    details = {
        "memory_recall_accuracy": recall,
        "memory_precision": precision,
        "n_memory_runs": int(len(memory_runs)),
        "n_runs": int(len(df)),
    }
    return score, passed, reason, details


def evaluate():
    return evaluate_suite("memory", _compute)


def main():
    print(json.dumps(evaluate().to_dict(), indent=2))


if __name__ == "__main__":
    main()
