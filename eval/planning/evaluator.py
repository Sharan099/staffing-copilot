"""Workflow Correctness, Multi-step Planning, State Transition Correctness."""

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

REFERENCE_WORKFLOW = [
    "authenticate_manager",
    "validate_request",
    "search_employees",
    "retrieve_skills",
    "check_availability",
    "retrieve_project_history",
    "rank_candidates",
    "generate_explanation",
    "await_manager_approval",
    "generate_final_report",
]


def _compute(df: pd.DataFrame):
    workflow_scores = []
    planning_scores = []
    transition_scores = []

    for _, row in df.iterrows():
        trace = row.get("agent_output", {}).get("trace", {})
        steps = trace.get("steps") or []
        step_names = [s["name"] for s in steps]
        expected = row.get("ground_truth", {}).get("workflow_steps") or REFERENCE_WORKFLOW

        workflow_scores.append(1.0 if step_names == expected else 0.8 if len(step_names) == len(expected) else 0.5)

        required = set(row.get("ground_truth", {}).get("expected_tools") or [])
        executed_tools = {s["tool"] for s in steps if s.get("tool")}
        if required:
            planning_scores.append(len(required & executed_tools) / len(required))
        else:
            planning_scores.append(1.0)

        legal = 1.0
        for i, step in enumerate(steps):
            if i > 0 and step["name"] == "authenticate_manager":
                legal = 0.0
        transition_scores.append(legal)

    wf = sum(workflow_scores) / len(workflow_scores)
    plan = sum(planning_scores) / len(planning_scores)
    trans = sum(transition_scores) / len(transition_scores)
    score = (wf + plan + trans) / 3 * 100
    passed = wf >= 0.85 and plan >= 0.85
    reason = f"Workflow {wf:.1%}, planning {plan:.1%}, transitions {trans:.1%}."
    details = {
        "workflow_correctness": wf,
        "multi_step_planning_accuracy": plan,
        "state_transition_correctness": trans,
        "n_runs": int(len(df)),
    }
    return score, passed, reason, details


def evaluate():
    return evaluate_suite("planning", _compute)


def main():
    print(json.dumps(evaluate().to_dict(), indent=2))


if __name__ == "__main__":
    main()
