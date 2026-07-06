"""Precision@K, Recall@K, MRR, NDCG@5."""

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
from eval.shared.grading import mrr, ndcg_at_k, precision_at_k, recall_at_k


def _compute(df: pd.DataFrame):
    p3, p5, r5, r10, mrr_vals, ndcg5 = [], [], [], [], [], []

    ranked_df = df[df["category"].isin(["normal", "edge", "e2e"])]
    if ranked_df.empty:
        ranked_df = df

    for _, row in ranked_df.iterrows():
        gt = row.get("ground_truth") or {}
        relevant = set(gt.get("relevant_employees") or [])
        ranking = row.get("agent_output", {}).get("ranking") or []
        if not relevant or not ranking:
            continue
        p3.append(precision_at_k(ranking, relevant, 3))
        p5.append(precision_at_k(ranking, relevant, 5))
        r5.append(recall_at_k(ranking, relevant, 5))
        r10.append(recall_at_k(ranking, relevant, 10))
        mrr_vals.append(mrr(ranking, relevant))
        ndcg5.append(ndcg_at_k(ranking, relevant, 5))

    if not p3:
        return 0.0, False, "No ranking evaluation data.", {"n_runs": 0}

    metrics = {
        "precision_at_3": sum(p3) / len(p3),
        "precision_at_5": sum(p5) / len(p5),
        "recall_at_5": sum(r5) / len(r5),
        "recall_at_10": sum(r10) / len(r10),
        "mrr": sum(mrr_vals) / len(mrr_vals),
        "ndcg_at_5": sum(ndcg5) / len(ndcg5),
    }
    score = sum(metrics.values()) / len(metrics) * 100
    passed = metrics["ndcg_at_5"] >= 0.80 and metrics["mrr"] >= 0.75
    reason = (
        f"P@3={metrics['precision_at_3']:.2f}, P@5={metrics['precision_at_5']:.2f}, "
        f"NDCG@5={metrics['ndcg_at_5']:.2f}, MRR={metrics['mrr']:.2f}."
    )
    details = {"metrics": metrics, "n_ranked_runs": len(p3)}
    return score, passed, reason, details


def evaluate():
    return evaluate_suite("ranking", _compute)


def main():
    print(json.dumps(evaluate().to_dict(), indent=2))


if __name__ == "__main__":
    main()
