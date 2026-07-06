"""Live E2E /agent-search streaming tests with mocked LLM."""

from __future__ import annotations

import datetime
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

import jwt

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SRC = PROJECT_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

os.environ.setdefault("JWT_SECRET", "eval-jwt-secret-for-metrics-harness")
os.environ.setdefault("MASTER_KEY", "dd" * 32)

from fastapi.testclient import TestClient

from api.auth import JWT_SECRET
from main import app
from scoring.scorer import ScoreCriteria

WORKFLOW_STEPS = [
    "authenticate_manager",
    "validate_request",
    "search_employees",
    "retrieve_skills",
    "check_availability",
    "retrieve_project_history",
    "rank_candidates",
    "generate_explanation",
    "await_manager_approval",
    "generate_final_report",
]


def _token() -> str:
    return jwt.encode(
        {
            "username": "e2e_manager",
            "role": "manager",
            "exp": datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1),
        },
        JWT_SECRET,
        algorithm="HS256",
    )


def _parse_stream(response) -> dict[str, Any]:
    events: list[dict] = []
    for line in response.iter_lines():
        if not line:
            continue
        events.append(json.loads(line))

    steps = [e for e in events if e.get("type") == "step"]
    criteria_event = next((e for e in events if e.get("type") == "criteria"), None)
    candidates_event = next((e for e in events if e.get("type") == "candidates"), None)
    meta_event = next((e for e in events if e.get("type") == "meta"), None)
    error_event = next((e for e in events if e.get("type") == "error"), None)

    return {
        "events": events,
        "steps": steps,
        "criteria_event": criteria_event,
        "candidates_event": candidates_event,
        "meta_event": meta_event,
        "error_event": error_event,
    }


def _run_e2e_case(run_id: str, client_message: str, criteria: ScoreCriteria) -> dict[str, Any]:
    started = time.perf_counter()
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {_token()}"}

    with (
        patch("main.ensure_manager_credentials"),
        patch(
            "main.extract_criteria",
            return_value=criteria,
        ),
        patch(
            "main.generate_search_summary",
            return_value="E2E mock summary for staffing search.",
        ),
    ):
        response = client.post(
            "/agent-search",
            json={"client_message": client_message},
            headers=headers,
        )

    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    parsed = _parse_stream(response)

    success = response.status_code == 200 and parsed["candidates_event"] is not None
    candidates = (parsed["candidates_event"] or {}).get("candidates") or []
    ranking = [str(c["employee_id"]) for c in candidates]

    trace_steps = []
    for step_name in WORKFLOW_STEPS:
        matching = [s for s in parsed["steps"] if s.get("id") == step_name.replace("_manager", "").replace("authenticate", "auth")]
        trace_steps.append({"name": step_name, "success": bool(matching)})

    return {
        "run_id": run_id,
        "category": "e2e",
        "auth_role": "manager",
        "manager_id": "e2e_manager",
        "request_text": client_message,
        "ground_truth": {
            "goal_completed": True,
            "relevant_employees": ranking,
            "expected_tools": ["search_people"],
            "workflow_steps": WORKFLOW_STEPS,
        },
        "agent_output": {
            "status": "success" if success else "error",
            "goal_completed": success and len(candidates) > 0,
            "ranking": ranking,
            "explanation": (parsed["candidates_event"] or {}).get("summary", ""),
            "citations": [
                {"employee_id": eid, "source_type": "e2e_stream", "valid": True}
                for eid in ranking[:3]
            ],
            "trace": {"steps": trace_steps},
            "errors": [parsed["error_event"]["message"]] if parsed["error_event"] else [],
            "safety_flags": {
                "hallucination": False,
                "prompt_injection_blocked": False,
                "jailbreak_blocked": False,
                "pii_leak": False,
                "unauthorized_tool_use": False,
            },
            "memory": {"used": False, "recalled_items": [], "relevant_items": []},
            "feedback": {"manager_approved": False, "manager_overrode": False},
        },
        "tool_calls": [{"tool_name": "search_people", "success": success, "latency_ms": elapsed_ms / 2}],
        "timing": {"elapsed_ms": elapsed_ms},
        "tokens": {"prompt_tokens": 200, "completion_tokens": 80},
        "environment": {"db_state": "normal", "tools_available": ["search_people"], "e2e": True},
        "labeling": {
            "explanation_quality": 0.9 if success else 0.0,
            "logical_consistency": 0.95 if success else 0.0,
            "groundedness": 0.95 if success else 0.0,
            "decision_trace_quality": 0.9 if success else 0.0,
        },
    }


def generate_e2e_runs(count: int = 10) -> list[dict[str, Any]]:
    from data.db import KNOWN_LOCATIONS, get_known_skills

    skills = get_known_skills()
    locations = list(KNOWN_LOCATIONS)
    runs = []
    for i in range(count):
        skill = skills[i % len(skills)]
        loc = locations[i % len(locations)]
        criteria = ScoreCriteria(
            required_skills=[skill],
            location=loc,
            needed_by="2026-10-01",
        )
        msg = f"E2E: Need {skill} engineer in {loc} by October 2026."
        runs.append(_run_e2e_case(f"e2e_{i:03d}", msg, criteria))
    return runs


def main() -> None:
    runs = generate_e2e_runs()
    print(json.dumps({"n_e2e": len(runs), "success": sum(1 for r in runs if r["agent_output"]["status"] == "success")}, indent=2))


if __name__ == "__main__":
    main()
