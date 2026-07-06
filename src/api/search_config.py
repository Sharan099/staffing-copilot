"""Merge LLM-extracted criteria with manager-provided search configuration."""

from __future__ import annotations

from scoring.scorer import ScoreCriteria, build_criteria
from scoring.skill_matching import CORE_SKILL_WEIGHT, NICE_TO_HAVE_WEIGHT


def build_skill_weights(
    required_skills: list[str],
    core_skills: list[str] | None = None,
) -> dict[str, int]:
    core_set = set(core_skills if core_skills is not None else required_skills)
    return {
        skill: CORE_SKILL_WEIGHT if skill in core_set else NICE_TO_HAVE_WEIGHT
        for skill in required_skills
    }


def merge_search_config(
    extracted: ScoreCriteria,
    search_config: dict | None,
) -> ScoreCriteria:
    if not search_config:
        return extracted

    skills = search_config.get("required_skills") or extracted.required_skills
    if not skills:
        skills = extracted.required_skills

    location = search_config.get("location")
    if location == "":
        location = None
    elif location is None:
        location = extracted.location

    needed_by = search_config.get("needed_by")
    if needed_by == "":
        needed_by = None
    elif needed_by is None:
        needed_by = extracted.needed_by

    core_skills = search_config.get("core_skills")
    skill_weights = build_skill_weights(skills, core_skills)

    scoring_weights = dict(
        search_config.get("scoring_weights") or extracted.scoring_weights.as_dict()
    )
    client_facing = bool(search_config.get("client_facing", extracted.client_facing))
    required_german = search_config.get("required_german_level")
    if required_german == "":
        required_german = None
    elif required_german is None:
        required_german = extracted.required_german_level

    if client_facing and not required_german:
        required_german = "B2"
    if client_facing and scoring_weights.get("language", 0) <= 0:
        scoring_weights["language"] = 15

    return build_criteria(
        required_skills=skills,
        location=location,
        needed_by=needed_by,
        skill_weights=skill_weights,
        scoring_weights=scoring_weights,
        client_facing=client_facing,
        required_german_level=required_german,
    )


def criteria_to_dict(criteria: ScoreCriteria) -> dict:
    return {
        "required_skills": criteria.required_skills,
        "location": criteria.location,
        "needed_by": criteria.needed_by,
        "skill_weights": criteria.skill_weights or {},
        "scoring_weights": criteria.scoring_weights.as_dict(),
        "client_facing": criteria.client_facing,
        "required_german_level": criteria.required_german_level,
    }
