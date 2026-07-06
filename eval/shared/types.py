"""Common types for evaluation run logs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class EvalResult:
    """Standard evaluator output."""

    metric: str
    score: float
    passed: bool
    reason: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "score": round(self.score, 2),
            "passed": self.passed,
            "reason": self.reason,
            "details": self.details,
        }


def result_to_json(result: EvalResult) -> dict[str, Any]:
    return result.to_dict()
