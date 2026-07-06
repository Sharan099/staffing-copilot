"""Read-only staffing decision memory from reports.db (approvals + rejections)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from data.db import get_reports_conn
from data.staffing_context import extract_staffing_context

_MEMORY_WINDOW_DAYS = 365


def ensure_rejections_schema(conn) -> None:
    conn.execute("""
    CREATE TABLE IF NOT EXISTS staffing_rejections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL,
        employee_name TEXT NOT NULL,
        rejected_by TEXT NOT NULL,
        rejected_at TEXT NOT NULL,
        client_name TEXT,
        domain TEXT,
        client_message TEXT DEFAULT '',
        manager_notes TEXT DEFAULT ''
    )
    """)
    conn.commit()


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _message_matches_domain(message: str, domain: str) -> bool:
    if domain == "general":
        return True
    return domain.lower() in (message or "").lower()


def _message_matches_client(message: str, client_name: str | None) -> bool:
    if not client_name:
        return False
    return client_name.lower() in (message or "").lower()


def get_staffing_memory(
    employee_id: int,
    employee_name: str,
    client_message: str,
) -> dict:
    """Return prior approvals/rejections relevant to this search (read-only)."""
    context = extract_staffing_context(client_message)
    domain = context["domain"] or "general"
    client_name = context["client_name"]
    cutoff = datetime.now(timezone.utc) - timedelta(days=_MEMORY_WINDOW_DAYS)

    memory_items: list[dict] = []
    similar_domain_count = 0
    rejected_for_client = False

    reports_conn = get_reports_conn()
    ensure_rejections_schema(reports_conn)

    approval_rows = reports_conn.execute(
        """
        SELECT approved_at, client_message, employee_name
        FROM reports
        WHERE employee_id = ?
        ORDER BY approved_at DESC
        LIMIT 20
        """,
        (employee_id,),
    ).fetchall()

    for approved_at, msg, name in approval_rows:
        ts = _parse_ts(approved_at)
        if ts and ts < cutoff:
            continue
        if _message_matches_domain(msg or "", domain):
            similar_domain_count += 1
            memory_items.append({
                "type": "prior_approval",
                "label": f"Staffed on similar {domain} project",
                "detail": f"{name} approved {approved_at[:10]} — {msg[:120]}",
                "at": approved_at,
            })

    rejection_rows = reports_conn.execute(
        """
        SELECT rejected_at, client_name, domain, client_message, manager_notes
        FROM staffing_rejections
        WHERE employee_id = ?
        ORDER BY rejected_at DESC
        LIMIT 10
        """,
        (employee_id,),
    ).fetchall()

    for rejected_at, rej_client, rej_domain, msg, notes in rejection_rows:
        ts = _parse_ts(rejected_at)
        if ts and ts < cutoff:
            continue
        match_client = client_name and rej_client and rej_client.lower() == client_name.lower()
        match_domain = rej_domain and rej_domain == domain
        if match_client or _message_matches_client(msg or "", client_name):
            rejected_for_client = True
            memory_items.append({
                "type": "prior_rejection",
                "label": f"Previously rejected for {client_name or rej_client or 'this client'}",
                "detail": (notes or msg or "No notes recorded.")[:200],
                "at": rejected_at,
            })
        elif match_domain:
            memory_items.append({
                "type": "prior_rejection",
                "label": f"Previously rejected for {domain} engagement",
                "detail": (notes or msg or "")[:200],
                "at": rejected_at,
            })

    summary_parts = []
    if similar_domain_count:
        summary_parts.append(
            f"Staffed on similar {domain} projects in the last {_MEMORY_WINDOW_DAYS // 30} months "
            f"({similar_domain_count} approval(s))"
        )
    if rejected_for_client:
        summary_parts.append(
            f"Previously rejected for {client_name or 'this client'} — review before re-proposing"
        )

    return {
        "domain": domain,
        "client_name": client_name,
        "similar_domain_approvals": similar_domain_count,
        "rejected_for_client": rejected_for_client,
        "summary": " · ".join(summary_parts) if summary_parts else "",
        "items": memory_items[:5],
    }


def log_rejection(
    employee_id: int,
    employee_name: str,
    rejected_by: str,
    client_message: str,
    manager_notes: str = "",
) -> int:
    context = extract_staffing_context(client_message)
    rejected_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    conn = get_reports_conn()
    ensure_rejections_schema(conn)
    cursor = conn.execute(
        """
        INSERT INTO staffing_rejections
        (employee_id, employee_name, rejected_by, rejected_at, client_name, domain, client_message, manager_notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            employee_id,
            employee_name,
            rejected_by,
            rejected_at,
            context["client_name"],
            context["domain"],
            client_message,
            manager_notes.strip(),
        ),
    )
    conn.commit()
    return cursor.lastrowid
