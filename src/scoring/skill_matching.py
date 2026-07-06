"""
Partial skill matching with weighted requirements and adjacent-skill credit.

Replaces binary all-or-nothing skill filters with transparent breakdowns:
matched skills, missing skills, and adjacent skills used for partial credit.
"""

from __future__ import annotations

from dataclasses import dataclass

# Weight per importance tier (core vs nice-to-have)
CORE_SKILL_WEIGHT = 2
NICE_TO_HAVE_WEIGHT = 1

# Points earned per weight unit for a direct skill match
POINTS_PER_WEIGHT_UNIT = 5

# Fraction of weighted points awarded when only an adjacent skill is present
ADJACENT_CREDIT_FRACTION = 0.5

# required skill -> related skills that earn partial credit when the required skill is missing
SKILL_ADJACENCY: dict[str, list[str]] = {
    "LangGraph": ["RAG", "LLM", "Python", "FastAPI", "MLOps"],
    "RAG": ["LLM", "LangGraph", "Python", "Vector DB", "PyTorch"],
    "LLM": ["RAG", "LangGraph", "Python", "PyTorch", "TensorFlow", "MLOps"],
    "FastAPI": ["Python", "Kubernetes", "Docker", "Go"],
    "Python": ["FastAPI", "RAG", "LLM", "MLOps", "TensorFlow"],
    "PyTorch": ["TensorFlow", "LLM", "RAG", "Computer Vision", "MLOps"],
    "TensorFlow": ["PyTorch", "LLM", "Computer Vision", "MLOps"],
    "Kubernetes": ["Docker", "Go", "MLOps", "FastAPI"],
    "Docker": ["Kubernetes", "Go", "MLOps"],
    "MLOps": ["Kubernetes", "Docker", "Python", "LLM"],
    "Go": ["Rust", "Kubernetes", "Docker"],
    "Rust": ["Go", "C++", "Embedded C"],
    "C++": ["Embedded C", "Rust", "AUTOSAR"],
    "Embedded C": ["C++", "AUTOSAR", "CAN Bus"],
    "AUTOSAR": ["Embedded C", "C++", "ISO 26262", "CAN Bus"],
    "CAN Bus": ["Embedded C", "AUTOSAR", "ISO 26262"],
    "ISO 26262": ["AUTOSAR", "Embedded C", "CAN Bus"],
    "Computer Vision": ["PyTorch", "TensorFlow", "Python"],
    "ROS": ["Python", "C++", "Computer Vision"],
}


@dataclass(frozen=True)
class AdjacentCredit:
    required: str
    via: str
    weight: int
    points: float

    def as_dict(self) -> dict:
        return {
            "required": self.required,
            "via": self.via,
            "weight": self.weight,
            "points": round(self.points, 1),
        }


@dataclass(frozen=True)
class SkillMatchResult:
    matched_skills: list[str]
    missing_skills: list[str]
    adjacent_credits: list[AdjacentCredit]
    points_earned: float
    points_possible: float
    match_percent: float

    def as_dict(self) -> dict:
        return {
            "matched_skills": self.matched_skills,
            "missing_skills": self.missing_skills,
            "adjacent_credits": [item.as_dict() for item in self.adjacent_credits],
            "points_earned": round(self.points_earned, 1),
            "points_possible": round(self.points_possible, 1),
            "match_percent": round(self.match_percent, 1),
        }


def expand_skills_for_pool(required_skills: list[str]) -> list[str]:
    """Skills used in DB pre-filter: any required skill or its adjacency neighbors."""
    pool: set[str] = set(required_skills)
    for skill in required_skills:
        pool.update(SKILL_ADJACENCY.get(skill, []))
    return sorted(pool)


def skill_weight(skill: str, weights: dict[str, int] | None) -> int:
    if weights and skill in weights:
        return weights[skill]
    return CORE_SKILL_WEIGHT


def compute_skill_match(
    candidate_skills: list[str],
    required_skills: list[str],
    skill_weights: dict[str, int] | None = None,
) -> SkillMatchResult:
    if not required_skills:
        return SkillMatchResult([], [], [], 0.0, 0.0, 100.0)

    skill_set = set(candidate_skills)
    used_skills: set[str] = set()
    matched: list[str] = []
    missing: list[str] = []
    adjacent_credits: list[AdjacentCredit] = []
    points_earned = 0.0
    points_possible = 0.0

    # Pass 1: direct matches
    direct_status: dict[str, bool] = {}
    for required in required_skills:
        weight = skill_weight(required, skill_weights)
        points_possible += weight * POINTS_PER_WEIGHT_UNIT
        if required in skill_set:
            matched.append(required)
            used_skills.add(required)
            points_earned += weight * POINTS_PER_WEIGHT_UNIT
            direct_status[required] = True
        else:
            direct_status[required] = False

    # Pass 2: adjacent credit for still-unmet requirements
    for required in required_skills:
        if direct_status[required]:
            continue
        weight = skill_weight(required, skill_weights)
        via = None
        for related in SKILL_ADJACENCY.get(required, []):
            if related in skill_set and related not in used_skills:
                via = related
                break
        if via:
            partial = weight * POINTS_PER_WEIGHT_UNIT * ADJACENT_CREDIT_FRACTION
            adjacent_credits.append(AdjacentCredit(required, via, weight, partial))
            used_skills.add(via)
            points_earned += partial
        else:
            missing.append(required)

    match_percent = (points_earned / points_possible * 100) if points_possible else 0.0
    return SkillMatchResult(
        matched_skills=matched,
        missing_skills=missing,
        adjacent_credits=adjacent_credits,
        points_earned=points_earned,
        points_possible=points_possible,
        match_percent=match_percent,
    )


def format_skill_match_detail(result: SkillMatchResult) -> str:
    parts = [
        f"{len(result.matched_skills)}/{len(result.matched_skills) + len(result.missing_skills) + len(result.adjacent_credits)} "
        f"skills covered ({result.match_percent:.0f}% weighted match)",
    ]
    if result.matched_skills:
        parts.append(f"Matched: {', '.join(result.matched_skills)}")
    if result.adjacent_credits:
        adj = ", ".join(f"{c.required} via {c.via}" for c in result.adjacent_credits)
        parts.append(f"Adjacent credit: {adj}")
    if result.missing_skills:
        parts.append(f"Missing: {', '.join(result.missing_skills)}")
    return " · ".join(parts)
