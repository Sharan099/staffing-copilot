"""Groundedness, Citation Accuracy, Source Attribution."""

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
    groundedness_vals = []
    citation_acc_vals = []
    attribution_vals = []

    for _, row in df.iterrows():
        ao = row.get("agent_output") or {}
        labeling = row.get("labeling") or {}
        ranking = set(ao.get("ranking") or [])
        citations = ao.get("citations") or []

        groundedness_vals.append(float(labeling.get("groundedness", 0)))

        if citations:
            valid = sum(1 for c in citations if c.get("valid") and c.get("employee_id") in ranking)
            citation_acc_vals.append(valid / len(citations))
            attribution_vals.append(1.0 if valid > 0 else 0.0)
        else:
            citation_acc_vals.append(0.0 if ranking else 1.0)
            attribution_vals.append(0.0 if ranking else 1.0)

    g = sum(groundedness_vals) / len(groundedness_vals)
    c = sum(citation_acc_vals) / len(citation_acc_vals)
    a = sum(attribution_vals) / len(attribution_vals)
    score = (g + c + a) / 3 * 100
    passed = g >= 0.85 and c >= 0.90
    reason = f"Groundedness {g:.1%}, citation accuracy {c:.1%}, attribution {a:.1%}."
    details = {
        "groundedness_score": g,
        "citation_accuracy": c,
        "source_attribution": a,
        "n_runs": int(len(df)),
    }
    return score, passed, reason, details


def evaluate():
    return evaluate_suite("grounding", _compute)


def main():
    print(json.dumps(evaluate().to_dict(), indent=2))


if __name__ == "__main__":
    main()
