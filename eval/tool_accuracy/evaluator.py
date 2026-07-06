"""Tool Selection Accuracy, Precision, Recall, Success Rate."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
_SRC = ROOT.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from eval.shared.base_evaluator import evaluate_suite


def _compute(df: pd.DataFrame):
    selection_hits = []
    precision_vals = []
    recall_vals = []
    success_vals = []

    for _, row in df.iterrows():
        expected = set(row.get("ground_truth", {}).get("expected_tools") or [])
        if not expected:
            continue
        calls = row.get("tool_calls") or []
        actual = [c["tool_name"] for c in calls]
        actual_set = set(actual)

        selection_hits.append(1.0 if expected.issubset(actual_set) else 0.0)
        tp = len(expected & actual_set)
        precision_vals.append(tp / len(expected) if expected else 0.0)
        recall_vals.append(tp / len(expected))
        if calls:
            ok = 0
            for c in calls:
                if c.get("success"):
                    ok += 1
                elif (c.get("output") or {}).get("error") == "permission_denied":
                    ok += 1
            success_vals.append(ok / len(calls))

    if not selection_hits:
        return 0.0, False, "No tool evaluation data.", {"n_runs": 0}

    selection_acc = sum(selection_hits) / len(selection_hits)
    precision = sum(precision_vals) / len(precision_vals)
    recall = sum(recall_vals) / len(recall_vals)
    tool_success = sum(success_vals) / len(success_vals) if success_vals else 0.0

    score = (selection_acc + precision + recall + tool_success) / 4 * 100
    passed = selection_acc >= 0.90 and tool_success >= 0.85
    reason = (
        f"Selection {selection_acc:.1%}, precision {precision:.1%}, "
        f"recall {recall:.1%}, tool success {tool_success:.1%}."
    )
    details = {
        "tool_selection_accuracy": selection_acc,
        "tool_precision": precision,
        "tool_recall": recall,
        "tool_success_rate": tool_success,
        "n_tool_runs": len(selection_hits),
        "n_runs": int(len(df)),
    }
    return score, passed, reason, details


def evaluate():
    return evaluate_suite("tool_accuracy", _compute)


def main():
    print(json.dumps(evaluate().to_dict(), indent=2))


if __name__ == "__main__":
    main()
