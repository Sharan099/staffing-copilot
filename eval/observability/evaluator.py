"""Trace completeness, tool logs, state logs, error logging."""

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
    trace_complete = []
    tool_logs = []
    state_logs = []
    error_logs = []

    for _, row in df.iterrows():
        ao = row.get("agent_output") or {}
        trace = ao.get("trace") or {}
        steps = trace.get("steps") or []
        trace_complete.append(1.0 if len(steps) >= 8 else len(steps) / 10)
        tool_logs.append(1.0 if row.get("tool_calls") is not None else 0.0)
        state_logs.append(1.0 if steps else 0.0)
        errs = ao.get("errors") or []
        status = ao.get("status")
        if status in ("error", "partial", "blocked"):
            error_logs.append(1.0 if errs else 0.0)
        else:
            error_logs.append(1.0)

    tc = sum(trace_complete) / len(trace_complete)
    tl = sum(tool_logs) / len(tool_logs)
    sl = sum(state_logs) / len(state_logs)
    el = sum(error_logs) / len(error_logs)
    score = (tc + tl + sl + el) / 4 * 100
    passed = tc >= 0.90 and tl >= 0.95
    reason = f"Trace {tc:.1%}, tool logs {tl:.1%}, state logs {sl:.1%}, error logs {el:.1%}."
    details = {
        "trace_completeness": tc,
        "tool_logs_present": tl,
        "state_logs_present": sl,
        "error_logging": el,
        "n_runs": int(len(df)),
    }
    return score, passed, reason, details


def evaluate():
    return evaluate_suite("observability", _compute)


def main():
    print(json.dumps(evaluate().to_dict(), indent=2))


if __name__ == "__main__":
    main()
