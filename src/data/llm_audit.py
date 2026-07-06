"""LLM request audit logging with PII redaction (GDPR data-flow trace)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from functools import lru_cache

from data.db import EMPLOYEE_FULL_NAME_SQL, get_reports_conn, get_staffing_conn

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


def ensure_llm_audit_schema(conn) -> None:
    conn.execute("""
    CREATE TABLE IF NOT EXISTS llm_request_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        manager_id TEXT NOT NULL,
        endpoint TEXT NOT NULL,
        provider TEXT,
        referenced_candidate_ids TEXT NOT NULL DEFAULT '[]',
        redacted_payload TEXT NOT NULL
    )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS gdpr_erasure_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        performed_by TEXT NOT NULL,
        candidate_id INTEGER NOT NULL,
        actions_taken TEXT NOT NULL
    )
    """)
    conn.commit()


@lru_cache(maxsize=1)
def _load_pii_index() -> tuple[dict[str, int], list[tuple[str, int]]]:
    """Build lookup maps: email -> id, and full names sorted longest-first for redaction."""
    conn = get_staffing_conn()
    try:
        rows = conn.execute(
            f"""
            SELECT employee_id, email, {EMPLOYEE_FULL_NAME_SQL} AS full_name
            FROM employees
            """
        ).fetchall()
    finally:
        conn.close()

    email_to_id: dict[str, int] = {}
    name_entries: list[tuple[str, int]] = []
    for employee_id, email, full_name in rows:
        if email:
            email_to_id[email.strip().lower()] = employee_id
        if full_name:
            name_entries.append((full_name.strip(), employee_id))

    name_entries.sort(key=lambda item: len(item[0]), reverse=True)
    return email_to_id, name_entries


def clear_pii_index_cache() -> None:
    _load_pii_index.cache_clear()


def redact_payload_for_audit(
    payload: dict | list | str,
    *,
    extra_candidate_ids: list[int] | None = None,
) -> tuple[str, list[int]]:
    """
    Replace candidate full names and emails with internal IDs before persisting logs.
    Returns (redacted_json, referenced_candidate_ids).
    """
    email_to_id, name_entries = _load_pii_index()
    referenced: set[int] = set(extra_candidate_ids or [])

    if isinstance(payload, str):
        text = payload
    else:
        text = json.dumps(payload, ensure_ascii=False, default=str)

    for email, employee_id in email_to_id.items():
        if email in text.lower():
            referenced.add(employee_id)
            pattern = re.compile(re.escape(email), re.IGNORECASE)
            text = pattern.sub(f"[candidate#{employee_id}]", text)

    for match in _EMAIL_RE.finditer(text):
        email = match.group(0).lower()
        employee_id = email_to_id.get(email)
        replacement = f"[candidate#{employee_id}]" if employee_id else "[redacted-email]"
        if employee_id:
            referenced.add(employee_id)
        text = text.replace(match.group(0), replacement)

    for full_name, employee_id in name_entries:
        if full_name and full_name in text:
            referenced.add(employee_id)
            text = text.replace(full_name, f"candidate#{employee_id}")

    for employee_id in referenced:
        text = re.sub(
            rf"#\s*{employee_id}\b",
            f"#{employee_id}",
            text,
        )

    return text, sorted(referenced)


def log_llm_request(
    *,
    manager_id: str,
    endpoint: str,
    provider: str | None,
    system: str | None,
    messages: list[dict],
    model: str | None = None,
    max_tokens: int | None = None,
    referenced_candidate_ids: list[int] | None = None,
) -> int:
    """Persist a redacted copy of the outbound LLM payload before the provider call."""
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": messages,
    }
    redacted, candidate_ids = redact_payload_for_audit(
        payload,
        extra_candidate_ids=referenced_candidate_ids,
    )
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    conn = get_reports_conn()
    ensure_llm_audit_schema(conn)
    cursor = conn.execute(
        """
        INSERT INTO llm_request_log
        (timestamp, manager_id, endpoint, provider, referenced_candidate_ids, redacted_payload)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            timestamp,
            manager_id,
            endpoint,
            provider,
            json.dumps(candidate_ids),
            redacted,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def delete_llm_logs_for_candidate(candidate_id: int) -> int:
    conn = get_reports_conn()
    ensure_llm_audit_schema(conn)
    rows = conn.execute(
        "SELECT id, referenced_candidate_ids FROM llm_request_log"
    ).fetchall()
    deleted = 0
    for row_id, ids_json in rows:
        try:
            ids = json.loads(ids_json or "[]")
        except json.JSONDecodeError:
            ids = []
        if candidate_id in ids:
            conn.execute("DELETE FROM llm_request_log WHERE id = ?", (row_id,))
            deleted += 1
    conn.commit()
    return deleted


def log_gdpr_erasure(
    *,
    performed_by: str,
    candidate_id: int,
    actions: list[str],
) -> int:
    conn = get_reports_conn()
    ensure_llm_audit_schema(conn)
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    cursor = conn.execute(
        """
        INSERT INTO gdpr_erasure_log (timestamp, performed_by, candidate_id, actions_taken)
        VALUES (?, ?, ?, ?)
        """,
        (timestamp, performed_by, candidate_id, json.dumps(actions)),
    )
    conn.commit()
    return cursor.lastrowid
