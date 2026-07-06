"""Full employee profile for manager view."""

from __future__ import annotations

from data.db import get_staffing_conn
from data.project_history import fetch_project_history


def get_employee_profile(employee_id: int) -> dict | None:
    conn = get_staffing_conn()
    try:
        row = conn.execute(
            """
            SELECT employee_id, first_name, last_name, email, title, seniority_level,
                   department, location, country, employment_type, hire_date,
                   years_experience, german_fluency, english_fluency, status,
                   current_utilization_pct, available_from, last_performance_rating
            FROM employees
            WHERE employee_id = ?
            """,
            (employee_id,),
        ).fetchone()
        if row is None:
            return None

        skills = conn.execute(
            """
            SELECT s.skill_name, s.category, es.proficiency_level, es.years_used
            FROM employee_skills es
            JOIN skills s ON s.skill_id = es.skill_id
            WHERE es.employee_id = ?
            ORDER BY es.years_used DESC, s.skill_name
            """,
            (employee_id,),
        ).fetchall()

        certs = conn.execute(
            """
            SELECT cert_name, issuing_body, issued_date, expiry_date
            FROM certifications
            WHERE employee_id = ?
            ORDER BY issued_date DESC
            """,
            (employee_id,),
        ).fetchall()

        allocations = conn.execute(
            """
            SELECT p.project_name, c.client_name, pa.role_on_project, pa.allocation_pct,
                   pa.start_date, pa.end_date, pa.status, p.location, p.delivery_model
            FROM project_allocations pa
            JOIN projects p ON p.project_id = pa.project_id
            LEFT JOIN clients c ON c.client_id = p.client_id
            WHERE pa.employee_id = ?
            ORDER BY pa.start_date DESC
            """,
            (employee_id,),
        ).fetchall()

        bench_rows = conn.execute(
            """
            SELECT bench_start_date, bench_end_date, reason
            FROM bench_periods
            WHERE employee_id = ?
            ORDER BY bench_start_date DESC
            """,
            (employee_id,),
        ).fetchall()
    finally:
        conn.close()

    status = row[14] or "billable"
    bench_info = None
    if status == "bench":
        if bench_rows:
            latest = bench_rows[0]
            bench_info = {
                "since": latest[0],
                "until": latest[1],
                "reason": latest[2] or "Awaiting new project assignment",
            }
        else:
            bench_info = {
                "since": row[16],
                "until": None,
                "reason": "On bench — no detailed reason recorded",
            }

    return {
        "employee_id": row[0],
        "first_name": row[1],
        "last_name": row[2],
        "name": f"{row[1]} {row[2]}",
        "email": row[3],
        "title": row[4],
        "seniority_level": row[5],
        "department": row[6],
        "location": row[7],
        "country": row[8],
        "employment_type": row[9],
        "hire_date": row[10],
        "years_experience": row[11],
        "german_fluency": row[12] or "none",
        "english_fluency": row[13] or "B2",
        "status": status,
        "current_utilization_pct": row[15],
        "available_from": row[16],
        "last_performance_rating": row[17],
        "skills": [
            {
                "skill_name": s[0],
                "category": s[1],
                "proficiency_level": s[2],
                "years_used": s[3],
            }
            for s in skills
        ],
        "certifications": [
            {
                "cert_name": c[0],
                "issuing_body": c[1],
                "issued_date": c[2],
                "expiry_date": c[3],
            }
            for c in certs
        ],
        "project_allocations": [
            {
                "project_name": a[0],
                "client_name": a[1],
                "role_on_project": a[2],
                "allocation_pct": a[3],
                "start_date": a[4],
                "end_date": a[5],
                "status": a[6],
                "location": a[7],
                "delivery_model": a[8],
            }
            for a in allocations
        ],
        "project_history": fetch_project_history(employee_id),
        "bench": bench_info,
        "bench_history": [
            {"start": b[0], "end": b[1], "reason": b[2]}
            for b in bench_rows
        ],
    }
