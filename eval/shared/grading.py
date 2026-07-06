"""Scoring helpers shared across evaluators."""

from __future__ import annotations

import math
from typing import Sequence


def clamp_score(value: float) -> float:
    return max(0.0, min(100.0, value))


def mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def precision_at_k(ranking: list[str], relevant: set[str], k: int) -> float:
    if k <= 0 or not ranking:
        return 0.0
    top_k = ranking[:k]
    hits = sum(1 for item in top_k if item in relevant)
    return hits / len(top_k)


def recall_at_k(ranking: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    top_k = ranking[:k]
    hits = sum(1 for item in top_k if item in relevant)
    return hits / len(relevant)


def mrr(ranking: list[str], relevant: set[str]) -> float:
    for index, item in enumerate(ranking, start=1):
        if item in relevant:
            return 1.0 / index
    return 0.0


def ndcg_at_k(ranking: list[str], relevant: set[str], k: int) -> float:
    dcg = 0.0
    for index, item in enumerate(ranking[:k], start=1):
        if item in relevant:
            dcg += 1.0 / math.log2(index + 1)
    ideal_hits = min(len(relevant), k)
    if ideal_hits == 0:
        return 0.0
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    return dcg / idcg if idcg else 0.0


def letter_grade(score: float) -> str:
    if score >= 97:
        return "A+"
    if score >= 93:
        return "A"
    if score >= 90:
        return "A-"
    if score >= 87:
        return "B+"
    if score >= 83:
        return "B"
    if score >= 80:
        return "B-"
    if score >= 77:
        return "C+"
    if score >= 73:
        return "C"
    if score >= 70:
        return "C-"
    return "F"
