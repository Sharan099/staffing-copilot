"""Minimize personal data sent to external LLM providers (GDPR data minimization)."""

from __future__ import annotations

import json
import re

from scoring.judgment import format_flags_for_prompt


def minimize_candidate_for_llm(candidate: dict) -> dict:
    """Staffing-relevant fields only — no name, email, or full HR profile."""
    skills = candidate.get("skills") or []
    if isinstance(skills, str):
        skills = [s.strip() for s in skills.split(",") if s.strip()]
    return {
        "candidate_id": candidate["employee_id"],
        "title": candidate.get("title"),
        "department": candidate.get("department"),
        "location": candidate.get("location"),
        "years_experience": candidate.get("years_experience"),
        "available_from": candidate.get("available_from"),
        "status": candidate.get("status"),
        "skills": skills[:12],
        "german_fluency": candidate.get("german_fluency"),
        "total_score": candidate.get("total_score"),
        "score_breakdown": candidate.get("score_breakdown"),
    }


def minimize_memory_for_llm(memory: dict, candidate_id: int) -> str:
    """Operational memory without employee name or free-text manager notes."""
    parts: list[str] = [f"candidate#{candidate_id}"]
    domain = memory.get("domain")
    if memory.get("similar_domain_approvals"):
        parts.append(
            f"{memory['similar_domain_approvals']} prior approval(s) in {domain or 'this'} domain"
        )
    if memory.get("rejected_for_client"):
        parts.append("previously rejected for this client")
    items = memory.get("items") or []
    for item in items[:3]:
        label = item.get("label")
        if label:
            parts.append(label)
    return " · ".join(parts[1:]) if len(parts) > 1 else "No prior staffing memory for this search."


def minimize_ranked_for_llm(ranked: list[dict]) -> list[dict]:
    slim: list[dict] = []
    for candidate in ranked:
        slim.append({
            "candidate_id": candidate["employee_id"],
            "total_score": candidate.get("total_score"),
            "title": candidate.get("title"),
            "location": candidate.get("location"),
            "years_experience": candidate.get("years_experience"),
            "available_from": candidate.get("available_from"),
            "judgment_flags": candidate.get("judgment_flags", []),
            "staffing_memory": minimize_memory_for_llm(
                candidate.get("staffing_memory") or {},
                candidate["employee_id"],
            ),
        })
    return slim


_CANDIDATE_REF_RE = re.compile(r"candidate#(\d+)", re.IGNORECASE)


def resolve_candidate_labels(text: str, name_by_id: dict[int, str]) -> str:
    """Replace candidate#ID tokens with real names after the LLM response (backend only)."""

    def _replace(match: re.Match) -> str:
        employee_id = int(match.group(1))
        return name_by_id.get(employee_id, match.group(0))

    return _CANDIDATE_REF_RE.sub(_replace, text)


def build_fit_summary_prompt(
    scored: dict,
    criteria,
    client_message: str,
) -> str:
    judgment_text = format_flags_for_prompt(scored.get("judgment_flags") or [])
    memory_text = minimize_memory_for_llm(
        scored.get("staffing_memory") or {},
        scored["employee_id"],
    )
    profile = minimize_candidate_for_llm(scored)
    return (
        f"Staffing request: {client_message}\n\n"
        f"Candidate: candidate#{scored['employee_id']}\n"
        f"Total score: {scored['total_score']}\n"
        f"Score breakdown: {json.dumps(profile.get('score_breakdown'))}\n"
        f"Profile (minimized): {json.dumps({k: v for k, v in profile.items() if k != 'score_breakdown'})}\n\n"
        f"Criteria: skills={criteria.required_skills}, "
        f"location={criteria.location}, needed_by={criteria.needed_by}\n\n"
        f"Judgment flags:\n{judgment_text}\n\n"
        f"Staffing memory:\n{memory_text}"
    )
