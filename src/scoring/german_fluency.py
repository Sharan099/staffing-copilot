"""German fluency levels and scoring for client-facing staffing roles."""

from __future__ import annotations

# Canonical CEFR + simplified labels used in UI and DB
GERMAN_FLUENCY_LEVELS = (
    "none",
    "A1",
    "A2",
    "basic",
    "B1",
    "B2",
    "business",
    "C1",
    "C2",
    "native",
)

# UI picker levels (aliases resolved at scoring time)
GERMAN_FLUENCY_PICKER_LEVELS = (
    "none",
    "A1",
    "A2",
    "B1",
    "B2",
    "C1",
    "C2",
    "native",
)

_ALIASES = {
    "basic": "A2",
    "business": "B2",
    "native": "C2",
}

_LEVEL_RANK = {
    "none": 0,
    "A1": 1,
    "A2": 2,
    "B1": 3,
    "B2": 4,
    "C1": 5,
    "C2": 6,
}


def normalize_german_level(level: str | None) -> str:
    if not level:
        return "none"
    cleaned = level.strip().lower()
    if cleaned in _ALIASES:
        return _ALIASES[cleaned]
    upper = level.strip().upper()
    if upper == "NONE":
        return "none"
    if upper in {"A1", "A2", "B1", "B2", "C1", "C2"}:
        return upper
    if cleaned == "native":
        return "C2"
    return "none"


def level_rank(level: str | None) -> int:
    return _LEVEL_RANK.get(normalize_german_level(level), 0)


def german_fluency_raw(
    candidate_level: str | None,
    required_level: str | None,
    client_facing: bool,
) -> tuple[float, str]:
    """
    Return (raw_score 0-100, human-readable detail).
    Neutral full score when role is not client-facing or no minimum set.
    """
    if not client_facing or not required_level:
        return 100.0, "German fluency not required for this role"

    cand_rank = level_rank(candidate_level)
    req_rank = level_rank(required_level)
    cand_label = normalize_german_level(candidate_level)
    req_label = normalize_german_level(required_level)

    if cand_rank >= req_rank:
        return 100.0, (
            f"German {cand_label} meets required {req_label} for client-facing role"
        )

    if req_rank == 0:
        return 100.0, f"German {cand_label} — no minimum required"

    ratio = cand_rank / req_rank
    raw = round(max(0.0, min(100.0, ratio * 100.0)), 1)
    gap = req_label if cand_rank == 0 else f"{cand_label} (need {req_label})"
    return raw, f"German fluency gap: {gap} → {raw:.0f}/100 raw for client-facing role"
