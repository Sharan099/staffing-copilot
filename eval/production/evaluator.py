"""Reliability, availability, error rate, crash rate, recovery rate."""

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
    errors = []
    crashes = []
    recoveries = []

    for _, row in df.iterrows():
        ao = row.get("agent_output") or {}
        status = ao.get("status")
        errs = ao.get("errors") or []

        errors.append(1.0 if status in ("error", "blocked") else 0.0)
        crashes.append(1.0 if status == "error" and not ao.get("ranking") else 0.0)
        if errs:
            recoveries.append(1.0 if status in ("partial", "expected_failure") else 0.0)
        else:
            recoveries.append(1.0)

    error_rate = sum(errors) / len(errors)
    crash_rate = sum(crashes) / len(crashes)
    recovery_rate = sum(recoveries) / len(recoveries)
    reliability = 1.0 - error_rate
    availability = 1.0 - crash_rate

    score = (reliability + availability + recovery_rate) / 3 * 100
    passed = reliability >= 0.90 and crash_rate <= 0.05
    reason = (
        f"Reliability {reliability:.1%}, availability {availability:.1%}, "
        f"error rate {error_rate:.1%}, recovery {recovery_rate:.1%}."
    )
    details = {
        "reliability": reliability,
        "availability": availability,
        "error_rate": error_rate,
        "crash_rate": crash_rate,
        "recovery_rate": recovery_rate,
        "n_runs": int(len(df)),
    }
    return score, passed, reason, details


def evaluate():
    return evaluate_suite("production", _compute)


def main():
    print(json.dumps(evaluate().to_dict(), indent=2))


if __name__ == "__main__":
    main()
