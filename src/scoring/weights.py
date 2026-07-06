"""Per-search dimension weights for candidate scoring (manager-adjustable)."""

from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass(frozen=True)
class ScoringWeights:
    skills: float = 40.0
    availability: float = 25.0
    experience: float = 15.0
    location: float = 10.0
    utilization: float = 10.0
    language: float = 0.0  # reserved for German fluency (step 3)

    def as_dict(self) -> dict[str, float]:
        return {field.name: getattr(self, field.name) for field in fields(self)}

    def normalized(self) -> ScoringWeights:
        values = [getattr(self, field.name) for field in fields(self)]
        total = sum(values)
        if total <= 0:
            return DEFAULT_SCORING_WEIGHTS
        factor = 100.0 / total
        return ScoringWeights(
            **{field.name: getattr(self, field.name) * factor for field in fields(self)}
        )


DEFAULT_SCORING_WEIGHTS = ScoringWeights()


def scoring_weights_from_dict(data: dict | None) -> ScoringWeights:
    if not data:
        return DEFAULT_SCORING_WEIGHTS
    merged = DEFAULT_SCORING_WEIGHTS.as_dict()
    for key, val in data.items():
        if val is not None and key in merged:
            merged[key] = float(val)
    return ScoringWeights(**merged).normalized()
