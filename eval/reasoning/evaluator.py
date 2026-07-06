"""Explanation Quality, Logical Consistency, Decision Trace Quality."""

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
    expl_scores = []
    logic_scores = []
    trace_scores = []

    for _, row in df.iterrows():
        labeling = row.get("labeling") or {}
        ao = row.get("agent_output") or {}
        ranking = ao.get("ranking") or []
        explanation = ao.get("explanation") or ""

        expl = float(labeling.get("explanation_quality", 0))
        logic = float(labeling.get("logical_consistency", 0))
        trace = float(labeling.get("decision_trace_quality", 0))

        if ranking and explanation and ranking[0] not in explanation:
            logic *= 0.8
        expl_scores.append(expl)
        logic_scores.append(logic)
        trace_scores.append(trace)

    eq = sum(expl_scores) / len(expl_scores) * 100
    lc = sum(logic_scores) / len(logic_scores) * 100
    dt = sum(trace_scores) / len(trace_scores) * 100
    score = (eq + lc + dt) / 3
    passed = score >= 75
    reason = f"Explanation {eq:.1f}, consistency {lc:.1f}, trace {dt:.1f}."
    details = {
        "explanation_quality": eq / 100,
        "logical_consistency": lc / 100,
        "decision_trace_quality": dt / 100,
        "n_runs": int(len(df)),
    }
    return score, passed, reason, details


def evaluate():
    return evaluate_suite("reasoning", _compute)


def main():
    print(json.dumps(evaluate().to_dict(), indent=2))


if __name__ == "__main__":
    main()
