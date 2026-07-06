"""Shared tool dispatch with safe outward-facing errors."""

from __future__ import annotations

import logging
import time

from api.auth import can_execute_tool
from tools.tools import (
    check_project_history,
    get_availability,
    search_people,
)

logger = logging.getLogger(__name__)

PUBLIC_TOOL_ERROR = "tool execution failed"
TOOL_PERMISSION_DENIED = "permission_denied"


def run_tool_call(call, caller_role: str | None = "manager") -> tuple[dict, str, float]:
    """Execute a tool call. Blocks read-only roles before any PII-bearing tool runs."""
    if not can_execute_tool(caller_role):
        return (
            {
                "error": TOOL_PERMISSION_DENIED,
                "detail": "Read-only roles cannot access employee data tools",
            },
            "forbidden",
            0.0,
        )

    start = time.time()
    try:
        if call.name == "search_people":
            result = search_people(
                call.input.get("required_skills", []),
                call.input.get("location"),
            )
        elif call.name == "get_availability":
            result = get_availability(call.input["required_availability"])
        elif call.name == "check_project_history":
            result = check_project_history(call.input["employee_name"])
        else:
            result = {"error": "unknown tool"}
        status = "success"
    except Exception:
        logger.exception("Tool %s failed", call.name)
        result = {"error": PUBLIC_TOOL_ERROR}
        status = "failed"

    duration_ms = round((time.time() - start) * 1000, 1)
    return result, status, duration_ms
