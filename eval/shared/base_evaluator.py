"""Base evaluator utilities."""

from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from eval.shared.grading import clamp_score
from eval.shared.io import load_runs
from eval.shared.types import EvalResult


def runs_to_dataframe(runs: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(runs) if runs else pd.DataFrame()


def evaluate_suite(
    metric: str,
    compute: Callable[[pd.DataFrame], tuple[float, bool, str, dict[str, Any]]],
    runs: list[dict[str, Any]] | None = None,
) -> EvalResult:
    runs = runs if runs is not None else load_runs()
    df = runs_to_dataframe(runs)
    if df.empty:
        return EvalResult(
            metric=metric,
            score=0.0,
            passed=False,
            reason="No evaluation runs found. Run eval/harness/generate_runs.py first.",
            details={"n_runs": 0},
        )
    score, passed, reason, details = compute(df)
    return EvalResult(metric=metric, score=clamp_score(score), passed=passed, reason=reason, details=details)
