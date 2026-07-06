"""Manager Approval Rate and Manager Override Rate."""

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
    approvals = []
    overrides = []
    for _, row in df.iterrows():
        fb = row.get("agent_output", {}).get("feedback") or {}
        if row.get("category") == "normal":
            approvals.append(1.0 if fb.get("manager_approved") else 0.0)
        overrides.append(1.0 if not fb.get("manager_overrode") else 0.0)

    approval_rate = sum(approvals) / len(approvals) if approvals else 1.0
    override_rate = 1.0 - (sum(overrides) / len(overrides))
    score = ((approval_rate * 0.7) + ((1 - override_rate) * 0.3)) * 100
    passed = approval_rate >= 0.70
    reason = f"Approval rate {approval_rate:.1%}, override rate {override_rate:.1%}."
    details = {
        "manager_approval_rate": approval_rate,
        "manager_override_rate": override_rate,
        "n_runs": int(len(df)),
    }
    return score, passed, reason, details


def evaluate():
    return evaluate_suite("hitl", _compute)


def main():
    print(json.dumps(evaluate().to_dict(), indent=2))


if __name__ == "__main__":
    main()
