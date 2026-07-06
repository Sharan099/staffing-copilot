"""GDPR right-to-erasure support for candidate records."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException

from data.db import get_reports_conn, get_staffing_conn
from data.llm_audit import (
    clear_pii_index_cache,
    delete_llm_logs_for_candidate,
    log_gdpr_erasure,
)


def gdpr_delete_candidate(candidate_id: int, performed_by: str) -> dict:
    """
    Delete a candidate and related records. Returns a non-PII confirmation for audit.
    """
    staffing = get_staffing_conn()
    try:
        exists = staffing.execute(
            "SELECT 1 FROM employees WHERE employee_id = ?",
            (candidate_id,),
        ).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="Candidate not found")

        actions: list[str] = []

        staffing.execute(
            "UPDATE employees SET manager_id = NULL WHERE manager_id = ?",
            (candidate_id,),
        )
        for table in (
            "employee_project_assignments",
            "bench_periods",
            "project_allocations",
            "certifications",
            "employee_skills",
        ):
            cursor = staffing.execute(
                f"DELETE FROM {table} WHERE employee_id = ?",
                (candidate_id,),
            )
            if cursor.rowcount:
                actions.append(f"deleted_{cursor.rowcount}_rows_from_{table}")

        cursor = staffing.execute(
            "DELETE FROM employees WHERE employee_id = ?",
            (candidate_id,),
        )
        if cursor.rowcount:
            actions.append("deleted_employee_row")
        staffing.commit()
    finally:
        staffing.close()

    reports = get_reports_conn()
    try:
        for table, column in (("reports", "employee_id"), ("staffing_rejections", "employee_id")):
            try:
                cursor = reports.execute(
                    f"DELETE FROM {table} WHERE {column} = ?",
                    (candidate_id,),
                )
                if cursor.rowcount:
                    actions.append(f"deleted_{cursor.rowcount}_rows_from_{table}")
            except Exception:
                pass
        reports.commit()
    finally:
        reports.close()

    llm_deleted = delete_llm_logs_for_candidate(candidate_id)
    if llm_deleted:
        actions.append(f"deleted_{llm_deleted}_llm_request_log_entries")

    clear_pii_index_cache()

    erasure_id = log_gdpr_erasure(
        performed_by=performed_by,
        candidate_id=candidate_id,
        actions=actions,
    )

    return {
        "erasure_id": erasure_id,
        "candidate_id": candidate_id,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "actions_taken": actions,
        "status": "completed",
    }
