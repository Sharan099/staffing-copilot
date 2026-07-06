"""Extract structured search criteria from natural-language staffing requests."""

from __future__ import annotations

import datetime
import json
import re

from api.llm_client import call_model_for_manager
from data.db import KNOWN_LOCATIONS, get_known_skills
from scoring.scorer import ScoreCriteria

_SKILL_HINTS = (
    "Python", "C++", "Embedded C", "AUTOSAR", "CAN Bus", "LLM", "RAG",
    "LangGraph", "TensorFlow", "PyTorch", "ISO 26262", "Kubernetes",
    "Go", "Rust", "ROS", "Computer Vision", "MLOps", "FastAPI",
)
_DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
_ROLE_COUNT_RE = re.compile(
    r"\b(\d+)\s+(?:senior\s+|junior\s+)?(?:ai\s+)?"
    r"(?:consultants?|engineers?|developers?|people|roles?)\b",
    re.IGNORECASE,
)
_WORD_COUNTS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
}


def _heuristic_extract(client_message: str) -> dict:
    lowered = client_message.lower()
    skills = [skill for skill in _SKILL_HINTS if skill.lower() in lowered]
    location = next(
        (city for city in KNOWN_LOCATIONS if city.lower() in lowered),
        None,
    )
    needed_by = _heuristic_needed_by(client_message)
    if not skills:
        skills = ["Python"]
    return {
        "required_skills": skills,
        "core_skills": list(skills),
        "location": location,
        "needed_by": needed_by,
        "role_count": _heuristic_role_count(client_message),
        "client_facing": _heuristic_client_facing(client_message),
        "required_german_level": _heuristic_german_level(client_message),
    }


def _heuristic_needed_by(client_message: str) -> str | None:
    date_match = _DATE_RE.search(client_message)
    if date_match:
        return date_match.group(1)
    lowered = client_message.lower()
    today = datetime.date.today()
    if any(phrase in lowered for phrase in ("asap", "immediately", "right away", "urgent")):
        return today.isoformat()
    if "next month" in lowered:
        year, month = today.year, today.month
        if month == 12:
            return datetime.date(year + 1, 1, 1).isoformat()
        return datetime.date(year, month + 1, 1).isoformat()
    if "next week" in lowered:
        return (today + datetime.timedelta(days=7)).isoformat()
    return None


def _heuristic_role_count(client_message: str) -> int:
    match = _ROLE_COUNT_RE.search(client_message)
    if match:
        return max(1, int(match.group(1)))
    lowered = client_message.lower()
    for word, count in _WORD_COUNTS.items():
        if re.search(
            rf"\b{word}\s+(?:senior\s+)?(?:ai\s+)?(?:engineers?|consultants?|developers?)",
            lowered,
        ):
            return count
    return 1


def _heuristic_client_facing(client_message: str) -> bool:
    lowered = client_message.lower()
    if any(
        phrase in lowered
        for phrase in (
            "client-facing",
            "client facing",
            "customer-facing",
            "on-site with client",
            "german speaking",
            "german-speaking",
            "fluent german",
            "business german",
        )
    ):
        return True
    return any(city in lowered for city in ("munich", "frankfurt", "hamburg", "berlin", "stuttgart"))


def _heuristic_german_level(client_message: str) -> str | None:
    lowered = client_message.lower()
    if "native german" in lowered or "german native" in lowered:
        return "native"
    if "business german" in lowered or "fluent german" in lowered:
        return "business"
    if "basic german" in lowered or "some german" in lowered:
        return "basic"
    if _heuristic_client_facing(client_message):
        return "business"
    return None


def _parse_llm_json(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.DOTALL).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _normalize_optional_field(value) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    lowered = s.lower()
    if lowered in {"null", "none", "n/a", "city or null"}:
        return None
    if lowered.endswith(" or null"):
        inner = s[: lowered.rfind(" or null")].strip()
        return inner if inner and inner.lower() not in {"null", "none"} else None
    return s


def _normalize_skills(raw_skills: list, known_skills: list[str]) -> list[str]:
    by_lower = {skill.lower(): skill for skill in known_skills}
    normalized: list[str] = []
    for skill in raw_skills:
        if not isinstance(skill, str):
            continue
        s = skill.strip()
        if not s:
            continue
        canonical = by_lower.get(s.lower())
        normalized.append(canonical if canonical else s)
    return normalized


def _normalize_german_level(value) -> str | None:
    raw = _normalize_optional_field(value)
    if not raw:
        return None
    aliases = {
        "a1": "basic",
        "a2": "basic",
        "b1": "basic",
        "b2": "business",
        "c1": "business",
        "c2": "native",
        "business": "business",
        "native": "native",
        "basic": "basic",
        "none": "none",
    }
    return aliases.get(raw.lower(), raw.lower())


def _normalize_role_count(value, fallback_text: str) -> int:
    if isinstance(value, int):
        return max(1, value)
    if isinstance(value, float):
        return max(1, int(value))
    if isinstance(value, str) and value.strip().isdigit():
        return max(1, int(value.strip()))
    return _heuristic_role_count(fallback_text)


def extract_request_for_form(client_message: str, manager_id: str) -> dict:
    """LLM + heuristics for the staffing request form (skills, location, date, headcount)."""
    known = get_known_skills()
    text = call_model_for_manager(
        manager_id,
        system=(
            "Extract staffing search criteria from the manager's request. "
            "Respond with JSON only, no markdown. Use null for unknown fields:\n"
            '{"required_skills": ["skill1"], "core_skills": ["skill1"], '
            '"location": null, "needed_by": "YYYY-MM-DD or null", '
            '"role_count": 1, "client_facing": false, "required_german_level": null}\n'
            f"Known locations: {', '.join(KNOWN_LOCATIONS)}. "
            "Map skills to known names when possible. "
            "Put must-have skills in core_skills; nice-to-have only in required_skills. "
            "role_count is the number of people/roles requested. "
            "needed_by must be ISO date when inferable (e.g. next month → first of next month). "
            "required_german_level: none, basic, business, or native when relevant."
        ),
        messages=[{"role": "user", "content": client_message}],
        max_tokens=400,
        endpoint="extract_request",
        referenced_candidate_ids=[],
    )
    payload = _parse_llm_json(text)
    if not payload:
        return _heuristic_extract(client_message)

    skills = _normalize_skills(payload.get("required_skills") or [], known)
    if not skills:
        return _heuristic_extract(client_message)

    core_skills = _normalize_skills(payload.get("core_skills") or [], known)
    if not core_skills:
        core_skills = list(skills)

    location = _normalize_optional_field(payload.get("location"))
    if location and location not in KNOWN_LOCATIONS:
        location = next(
            (city for city in KNOWN_LOCATIONS if city.lower() == location.lower()),
            None,
        )

    needed_by = _normalize_optional_field(payload.get("needed_by"))
    if not needed_by:
        needed_by = _heuristic_needed_by(client_message)

    german = _normalize_german_level(payload.get("required_german_level"))
    if not german and payload.get("client_facing"):
        german = "business"

    client_facing = bool(payload.get("client_facing")) or bool(german and german != "none")
    if not client_facing:
        client_facing = _heuristic_client_facing(client_message)
    if client_facing and not german:
        german = _heuristic_german_level(client_message) or "business"

    return {
        "required_skills": skills,
        "core_skills": core_skills,
        "location": location,
        "needed_by": needed_by,
        "role_count": _normalize_role_count(payload.get("role_count"), client_message),
        "client_facing": client_facing,
        "required_german_level": german,
    }


def extract_criteria(client_message: str, manager_id: str) -> ScoreCriteria:
    data = extract_request_for_form(client_message, manager_id)
    return ScoreCriteria(
        required_skills=data["required_skills"],
        location=data["location"],
        needed_by=data["needed_by"],
    )
