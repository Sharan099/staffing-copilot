"""JWT authentication helpers."""

from __future__ import annotations

import datetime

import jwt
from fastapi import Header, HTTPException

from api.config import get_jwt_secret

JWT_SECRET = get_jwt_secret()


def check_auth(authorization: str = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.replace("Bearer ", "")
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired, please log in again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_manager(payload: dict) -> None:
    if payload.get("role") != "manager":
        raise HTTPException(status_code=403, detail="Only managers can approve hires")


# Roles allowed to execute employee-data tools (PII-bearing).
ALLOWED_TOOL_ROLES = frozenset({"manager", "admin"})
READ_ONLY_ROLES = frozenset({"viewer", "read_only"})

# All registered agent tools return employee PII.
PII_EMPLOYEE_TOOLS = frozenset({
    "search_people",
    "get_availability",
    "check_project_history",
})


def can_execute_tool(caller_role: str | None) -> bool:
    """Return True only for roles permitted to run employee-data tools."""
    return (caller_role or "").lower() in ALLOWED_TOOL_ROLES


def is_read_only_role(caller_role: str | None) -> bool:
    role = (caller_role or "").lower()
    if not role:
        return True
    return role in READ_ONLY_ROLES or role not in ALLOWED_TOOL_ROLES
