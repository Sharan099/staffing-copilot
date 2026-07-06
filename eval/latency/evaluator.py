"""End-to-end latency, tool latency, token usage, cost, efficiency."""

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

COST_PER_1K_PROMPT = 0.003
COST_PER_1K_COMPLETION = 0.015
LATENCY_THRESHOLD_MS = 5000


def _compute(df: pd.DataFrame):
    e2e = []
    tool_lat = []
    tokens = []
    costs = []
    efficiency = []

    for _, row in df.iterrows():
        timing = row.get("timing") or {}
        e2e.append(float(timing.get("elapsed_ms", 0)))
        calls = row.get("tool_calls") or []
        if calls:
            tool_lat.append(sum(c.get("latency_ms", 0) for c in calls) / len(calls))
        tok = row.get("tokens") or {}
        pt = float(tok.get("prompt_tokens", 0))
        ct = float(tok.get("completion_tokens", 0))
        tokens.append(pt + ct)
        costs.append(pt / 1000 * COST_PER_1K_PROMPT + ct / 1000 * COST_PER_1K_COMPLETION)
        success = row.get("agent_output", {}).get("status") in ("success", "partial")
        efficiency.append(1.0 if success and (pt + ct) < 5000 else 0.5 if success else 0.0)

    avg_e2e = sum(e2e) / len(e2e)
    avg_tool = sum(tool_lat) / len(tool_lat) if tool_lat else 0.0
    avg_tokens = sum(tokens) / len(tokens)
    avg_cost = sum(costs) / len(costs)
    eff = sum(efficiency) / len(efficiency)

    latency_score = max(0.0, 1.0 - avg_e2e / LATENCY_THRESHOLD_MS)
    score = (latency_score * 0.4 + eff * 0.3 + min(1.0, 2000 / max(avg_tokens, 1)) * 0.3) * 100
    passed = avg_e2e <= LATENCY_THRESHOLD_MS
    reason = f"Avg E2E {avg_e2e:.0f}ms, tool {avg_tool:.0f}ms, tokens {avg_tokens:.0f}, cost ${avg_cost:.4f}."
    details = {
        "end_to_end_latency_ms": avg_e2e,
        "tool_latency_ms": avg_tool,
        "average_token_usage": avg_tokens,
        "api_cost_usd": avg_cost,
        "token_efficiency": eff,
        "n_runs": int(len(df)),
    }
    return score, passed, reason, details


def evaluate():
    return evaluate_suite("latency", _compute)


def main():
    print(json.dumps(evaluate().to_dict(), indent=2))


if __name__ == "__main__":
    main()
