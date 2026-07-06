"""Judgment-layer flags computed from project history and staffing memory."""

from __future__ import annotations

from datetime import date


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _has_burnout_risk(projects: list[dict]) -> tuple[bool, str]:
    """Two or more consecutive projects with no gap between end and next start."""
    if len(projects) < 2:
        return False, ""
    consecutive = 0
    max_streak = 0
    details: list[str] = []
    for index in range(1, len(projects)):
        prev_end = _parse_date(projects[index - 1]["end_date"])
        curr_start = _parse_date(projects[index]["start_date"])
        if prev_end and curr_start:
            gap = (curr_start - prev_end).days
            if gap <= 0:
                consecutive += 1
                max_streak = max(max_streak, consecutive + 1)
                details.append(
                    f"{projects[index - 1]['client_name']} → {projects[index]['client_name']} (no gap)"
                )
            else:
                consecutive = 0
    if max_streak >= 2:
        return True, "; ".join(details[:2])
    return False, ""


def _repeat_domain_pattern(
    projects: list[dict],
    domain: str,
    client_name: str | None,
) -> tuple[bool, str]:
    """Nth project in domain but first time with this specific client."""
    if domain == "general":
        return False, ""
    in_domain = [p for p in projects if p.get("domain") == domain]
    if len(in_domain) < 2:
        return False, ""
    if not client_name:
        return False, ""
    prior_clients = {p["client_name"] for p in in_domain}
    if client_name in prior_clients:
        return False, ""
    return True, (
        f"{len(in_domain)} prior {domain} project(s) with other clients "
        f"({', '.join(sorted(prior_clients)[:3])}); first time with {client_name}"
    )


def compute_judgment_flags(
    projects: list[dict],
    staffing_memory: dict,
    domain: str,
    client_name: str | None,
) -> list[dict]:
    flags: list[dict] = []

    burnout, burnout_detail = _has_burnout_risk(projects)
    if burnout:
        flags.append({
            "id": "burnout_risk",
            "severity": "high",
            "label": "Burnout risk",
            "detail": f"Back-to-back project assignments with no recovery gap: {burnout_detail}",
        })

    repeat, repeat_detail = _repeat_domain_pattern(projects, domain, client_name)
    if repeat:
        flags.append({
            "id": "repeat_domain_pattern",
            "severity": "medium",
            "label": "Repeat domain pattern",
            "detail": repeat_detail,
        })

    if staffing_memory.get("rejected_for_client"):
        flags.append({
            "id": "turned_down_before",
            "severity": "high",
            "label": "Previously rejected for this client",
            "detail": staffing_memory.get("summary") or "Prior rejection on record for this client.",
        })

    if staffing_memory.get("similar_domain_approvals") and not repeat:
        count = staffing_memory["similar_domain_approvals"]
        flags.append({
            "id": "domain_experience",
            "severity": "low",
            "label": "Domain track record",
            "detail": (
                f"Approved for {count} similar {domain} engagement(s) in the past year — "
                "institutional familiarity"
            ),
        })

    return flags


def enrich_candidate(candidate: dict, client_message: str) -> dict:
    from data.project_history import fetch_project_history
    from data.staffing_memory import get_staffing_memory

    projects = fetch_project_history(candidate["employee_id"])
    memory = get_staffing_memory(
        candidate["employee_id"],
        candidate["name"],
        client_message,
    )
    flags = compute_judgment_flags(
        projects,
        memory,
        memory.get("domain") or "general",
        memory.get("client_name"),
    )
    candidate = dict(candidate)
    candidate["project_history"] = projects
    candidate["staffing_memory"] = memory
    candidate["judgment_flags"] = flags
    return candidate


def enrich_ranked_candidates(ranked: list[dict], client_message: str) -> list[dict]:
    return [enrich_candidate(c, client_message) for c in ranked]


def format_flags_for_prompt(flags: list[dict]) -> str:
    if not flags:
        return "No judgment flags."
    return "\n".join(f"- [{f['severity'].upper()}] {f['label']}: {f['detail']}" for f in flags)
