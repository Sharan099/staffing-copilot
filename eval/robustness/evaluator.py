"""Robustness: invalid input, empty DB, timeouts, retries, fallbacks."""

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
    invalid_handling = []
    empty_db = []
    timeout_recovery = []
    fallback = []

    for _, row in df.iterrows():
        ao = row.get("agent_output") or {}
        env = row.get("environment") or {}
        status = ao.get("status")
        errors = ao.get("errors") or []

        if row.get("category") == "failure":
            invalid_handling.append(1.0 if status in {"error", "expected_failure", "partial"} else 0.0)
        else:
            invalid_handling.append(1.0)

        if env.get("db_state") == "empty":
            empty_db.append(1.0 if status in {"partial", "error", "expected_failure"} else 0.0)

        tool_calls = row.get("tool_calls") or []
        failed_tools = [t for t in tool_calls if not t.get("success")]
        if failed_tools:
            timeout_recovery.append(1.0 if status != "success" or errors else 0.5)
            fallback.append(1.0 if ao.get("ranking") or errors else 0.0)
        else:
            timeout_recovery.append(1.0)
            fallback.append(1.0)

    def avg(vals):
        return sum(vals) / len(vals) if vals else 1.0

    ih, ed, tr, fb = avg(invalid_handling), avg(empty_db) if empty_db else 1.0, avg(timeout_recovery), avg(fallback)
    score = (ih + ed + tr + fb) / 4 * 100
    passed = ih >= 0.85 and tr >= 0.80
    reason = f"Invalid input {ih:.1%}, empty DB {ed:.1%}, recovery {tr:.1%}, fallback {fb:.1%}."
    details = {
        "invalid_input_handling": ih,
        "empty_database_handling": ed,
        "tool_timeout_recovery": tr,
        "fallback_success_rate": fb,
        "n_runs": int(len(df)),
    }
    return score, passed, reason, details


def evaluate():
    return evaluate_suite("robustness", _compute)


def main():
    print(json.dumps(evaluate().to_dict(), indent=2))


if __name__ == "__main__":
    main()
