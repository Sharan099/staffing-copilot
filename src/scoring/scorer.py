"""
Transparent, reproducible candidate scoring with per-search dimension weights.

Each dimension produces a raw score (0–100), multiplied by the manager's
weight for that search. Breakdown shows raw × weight = contribution so
managers can see why one candidate outranks another.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from scoring.german_fluency import german_fluency_raw
from scoring.skill_matching import (
    compute_skill_match,
    format_skill_match_detail,
)
from scoring.weights import (
    DEFAULT_SCORING_WEIGHTS,
    ScoringWeights,
    scoring_weights_from_dict,
)

# Raw-score caps for experience dimension (0–100 scale)
MAX_EXPERIENCE_YEARS_FOR_FULL_SCORE = 15
BENCH_UTILIZATION_RAW = 100.0
MAX_UTILIZATION_RAW_FROM_PCT = 100.0


@dataclass(frozen=True)
class ScoreCriteria:
    required_skills: list[str]
    location: str | None = None
    needed_by: str | None = None  # YYYY-MM-DD
    skill_weights: dict[str, int] | None = field(default=None)
    scoring_weights: ScoringWeights = field(default_factory=lambda: DEFAULT_SCORING_WEIGHTS)
    client_facing: bool = False
    required_german_level: str | None = None  # minimum CEFR when client_facing


def _parse_iso(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _days_between(earlier: date, later: date) -> int:
    return (later - earlier).days


def _experience_raw(years: int) -> float:
    return min(100.0, (years / MAX_EXPERIENCE_YEARS_FOR_FULL_SCORE) * 100.0)


def _location_raw(candidate_location: str | None, requested: str | None) -> float:
    if not requested:
        return 100.0
    return 100.0 if candidate_location == requested else 0.0


def _availability_raw(available_from: date | None, needed_by: date | None, available_str: str | None) -> float:
    if needed_by and available_from:
        if available_from <= needed_by:
            days_early = _days_between(available_from, needed_by)
            bonus = min(20.0, (days_early // 30) * 5)
            return min(100.0, 80.0 + bonus)
        days_late = _days_between(needed_by, available_from)
        penalty = min(100.0, (days_late // 30) * 15)
        return max(0.0, 100.0 - penalty)
    if available_str:
        return 50.0
    return 0.0


def _utilization_raw(status: str, utilization_pct: int) -> float:
    if status == "bench":
        return BENCH_UTILIZATION_RAW
    return min(MAX_UTILIZATION_RAW_FROM_PCT, max(0.0, 100.0 - utilization_pct))


def _breakdown_row(
    rule: str,
    raw_score: float,
    weight_percent: float,
    detail: str,
    extra: dict | None = None,
) -> dict:
    weighted = round(raw_score * weight_percent / 100.0, 1)
    row = {
        "rule": rule,
        "raw_score": round(raw_score, 1),
        "weight_percent": round(weight_percent, 1),
        "weighted_points": weighted,
        "points": int(round(weighted)),  # backward-compatible total sum field
        "detail": detail,
    }
    if extra:
        row.update(extra)
    return row


def score_candidate(candidate: dict, criteria: ScoreCriteria) -> dict:
    weights = criteria.scoring_weights.normalized()
    breakdown: list[dict] = []

    skill_result = compute_skill_match(
        candidate.get("skills", []),
        criteria.required_skills,
        criteria.skill_weights,
    )
    skills_raw = skill_result.match_percent
    breakdown.append(_breakdown_row(
        "skills",
        skills_raw,
        weights.skills,
        format_skill_match_detail(skill_result),
        {"skill_match": skill_result.as_dict()},
    ))

    years = int(candidate.get("years_experience") or 0)
    exp_raw = _experience_raw(years)
    breakdown.append(_breakdown_row(
        "experience",
        exp_raw,
        weights.experience,
        f"{years} years experience → {exp_raw:.0f}/100 raw (full score at {MAX_EXPERIENCE_YEARS_FOR_FULL_SCORE}+ yrs)",
    ))

    loc_raw = _location_raw(candidate.get("location"), criteria.location)
    if criteria.location:
        loc_detail = (
            f"location matches {criteria.location}"
            if loc_raw == 100
            else f"location {candidate.get('location')} ≠ requested {criteria.location}"
        )
    else:
        loc_detail = "no location preference — neutral full raw score"
    breakdown.append(_breakdown_row("location", loc_raw, weights.location, loc_detail))

    available_from = _parse_iso(candidate.get("available_from"))
    needed_by = _parse_iso(criteria.needed_by)
    avail_raw = _availability_raw(available_from, needed_by, candidate.get("available_from"))
    if needed_by and available_from:
        if available_from <= needed_by:
            avail_detail = (
                f"available {candidate['available_from']} on/before {criteria.needed_by} "
                f"→ {avail_raw:.0f}/100 raw"
            )
        else:
            avail_detail = (
                f"available {candidate['available_from']} after needed-by {criteria.needed_by} "
                f"→ {avail_raw:.0f}/100 raw"
            )
    elif candidate.get("available_from"):
        avail_detail = f"no deadline; baseline raw {avail_raw:.0f}/100 for known date"
    else:
        avail_detail = "availability date unknown → 0 raw"
    breakdown.append(_breakdown_row("availability", avail_raw, weights.availability, avail_detail))

    status = candidate.get("status", "")
    utilization = int(candidate.get("current_utilization_pct") or 100)
    util_raw = _utilization_raw(status, utilization)
    util_detail = (
        f"bench status → {util_raw:.0f}/100 raw"
        if status == "bench"
        else f"utilization {utilization}% → {util_raw:.0f}/100 raw capacity"
    )
    breakdown.append(_breakdown_row("utilization", util_raw, weights.utilization, util_detail))

    lang_weight = weights.language
    if criteria.client_facing or lang_weight > 0:
        lang_raw, lang_detail = german_fluency_raw(
            candidate.get("german_fluency"),
            criteria.required_german_level,
            criteria.client_facing,
        )
        breakdown.append(_breakdown_row(
            "language",
            lang_raw,
            lang_weight,
            lang_detail,
        ))

    total = round(sum(item["weighted_points"] for item in breakdown), 1)
    return {
        "employee_id": candidate["employee_id"],
        "name": candidate["name"],
        "title": candidate.get("title"),
        "department": candidate.get("department"),
        "location": candidate.get("location"),
        "years_experience": years,
        "available_from": candidate.get("available_from"),
        "status": status,
        "skills": candidate.get("skills", []),
        "german_fluency": candidate.get("german_fluency", "none"),
        "skill_match": skill_result.as_dict(),
        "scoring_weights": weights.as_dict(),
        "total_score": total,
        "score_breakdown": breakdown,
    }


def rank_candidates(
    candidates: list[dict],
    criteria: ScoreCriteria,
    top_n: int = 5,
) -> list[dict]:
    scored = [score_candidate(candidate, criteria) for candidate in candidates]
    scored.sort(
        key=lambda item: (
            -item["total_score"],
            item["available_from"] or "9999",
            -item["years_experience"],
            item["employee_id"],
        )
    )
    for index, item in enumerate(scored[:top_n], start=1):
        item["rank"] = index
    return scored[:top_n]


def build_criteria(
    required_skills: list[str],
    location: str | None = None,
    needed_by: str | None = None,
    skill_weights: dict[str, int] | None = None,
    scoring_weights: dict | ScoringWeights | None = None,
    client_facing: bool = False,
    required_german_level: str | None = None,
) -> ScoreCriteria:
    weights = (
        scoring_weights
        if isinstance(scoring_weights, ScoringWeights)
        else scoring_weights_from_dict(scoring_weights)
    )
    if client_facing and not required_german_level:
        required_german_level = "B2"
    return ScoreCriteria(
        required_skills=required_skills,
        location=location,
        needed_by=needed_by,
        skill_weights=skill_weights,
        scoring_weights=weights,
        client_facing=client_facing,
        required_german_level=required_german_level,
    )
