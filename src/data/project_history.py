"""Employee project assignment history for judgment-layer flags."""

from __future__ import annotations

import random
from datetime import date, timedelta

from data.db import get_staffing_conn

CLIENTS = ("BMW", "Bosch", "Siemens Healthineers", "Continental", "SAP", "Mercedes")
DOMAINS = ("automotive", "healthcare", "manufacturing", "software", "mobility")


def _seed_projects_for_employee(employee_id: int) -> list[tuple]:
    rng = random.Random(employee_id * 97)
    count = rng.randint(2, 4)
    rows: list[tuple] = []
    cursor = date(2022, 6, 1) + timedelta(days=rng.randint(0, 120))

    for index in range(count):
        duration = rng.randint(120, 400)
        end = cursor + timedelta(days=duration)
        # ~14% of employees: back-to-back assignments (burnout pattern)
        gap_days = 0 if employee_id % 7 == 0 else rng.randint(7, 45)
        rows.append((
            employee_id,
            rng.choice(CLIENTS),
            rng.choice(DOMAINS),
            "Senior Engineer" if index else "Engineer",
            cursor.isoformat(),
            end.isoformat(),
        ))
        cursor = end + timedelta(days=gap_days)

    return rows


def ensure_project_history_schema(conn) -> None:
    conn.execute("""
    CREATE TABLE IF NOT EXISTS employee_project_assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL,
        client_name TEXT NOT NULL,
        domain TEXT NOT NULL,
        role_title TEXT,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL
    )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_project_employee ON employee_project_assignments(employee_id)"
    )
    count = conn.execute("SELECT COUNT(*) FROM employee_project_assignments").fetchone()[0]
    if count > 0:
        return

    employee_ids = [row[0] for row in conn.execute("SELECT employee_id FROM employees").fetchall()]
    for employee_id in employee_ids:
        for row in _seed_projects_for_employee(employee_id):
            conn.execute(
                """
                INSERT INTO employee_project_assignments
                (employee_id, client_name, domain, role_title, start_date, end_date)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                row,
            )
    conn.commit()


def fetch_project_history(employee_id: int) -> list[dict]:
    conn = get_staffing_conn()
    try:
        ensure_project_history_schema(conn)
        rows = conn.execute(
            """
            SELECT client_name, domain, role_title, start_date, end_date
            FROM employee_project_assignments
            WHERE employee_id = ?
            ORDER BY start_date
            """,
            (employee_id,),
        ).fetchall()
        return [
            {
                "client_name": row[0],
                "domain": row[1],
                "role_title": row[2],
                "start_date": row[3],
                "end_date": row[4],
            }
            for row in rows
        ]
    finally:
        conn.close()
