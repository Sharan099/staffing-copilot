import re

from data.db import (
    EMPLOYEE_FULL_NAME_SQL,
    EMPLOYEE_FULL_NAME_SQL_E,
    KNOWN_LOCATIONS,
    get_staffing_conn,
)
from scoring.skill_matching import expand_skills_for_pool

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_EMPLOYEE_RANKING_SELECT = f"""
    employee_id, {EMPLOYEE_FULL_NAME_SQL} AS name, title, department, location,
    years_experience, current_utilization_pct, available_from, status,
    COALESCE(german_fluency, 'none') AS german_fluency
"""


def _employee_row(row, extra=None):
    result = {
        "name": row[0],
        "title": row[1],
        "department": row[2],
        "location": row[3],
        "available_from": row[4],
    }
    if extra:
        result.update(extra)
    return result


def _search_row_from_ranking_row(row):
    """Map full ranking SELECT row to search_people result shape."""
    return {
        "name": row[1],
        "title": row[2],
        "department": row[3],
        "location": row[4],
        "available_from": row[7],
    }


def _split_skills_and_location(required_skills, location=None):
    skills = [s.strip() for s in (required_skills or []) if s and s.strip()]
    if location:
        loc = location.strip()
        if loc.lower() in {"null", "none", "city or null"} or " or null" in loc.lower():
            loc = None
        elif loc not in KNOWN_LOCATIONS:
            matched = next((c for c in KNOWN_LOCATIONS if c.lower() == loc.lower()), None)
            loc = matched
        if loc:
            return skills, loc

    extracted = [s for s in skills if s in KNOWN_LOCATIONS]
    if not extracted:
        return skills, None

    return [s for s in skills if s not in KNOWN_LOCATIONS], extracted[0]


def _fetch_skills_for_employee(conn, employee_id):
    rows = conn.execute(
        """
        SELECT s.skill_name
        FROM employee_skills es
        JOIN skills s ON es.skill_id = s.skill_id
        WHERE es.employee_id = ?
        ORDER BY s.skill_name
        """,
        (employee_id,),
    ).fetchall()
    return [row[0] for row in rows]


def _fetch_skills_for_employee_by_name(conn, employee_name):
    rows = conn.execute(
        f"""
        SELECT s.skill_name
        FROM employees e
        JOIN employee_skills es ON e.employee_id = es.employee_id
        JOIN skills s ON es.skill_id = s.skill_id
        WHERE LOWER({EMPLOYEE_FULL_NAME_SQL_E}) = LOWER(?)
        ORDER BY s.skill_name
        """,
        (employee_name,),
    ).fetchall()
    return [row[0] for row in rows]


def _ranking_row(conn, row):
    employee_id = row[0]
    return {
        "employee_id": employee_id,
        "name": row[1],
        "title": row[2],
        "department": row[3],
        "location": row[4],
        "years_experience": row[5],
        "current_utilization_pct": row[6],
        "available_from": row[7],
        "status": row[8],
        "german_fluency": row[9] if len(row) > 9 else "none",
        "skills": _fetch_skills_for_employee(conn, employee_id),
    }


def _fetch_candidates_by_skills(conn, skills, location=None):
    """Return employees with at least one required or adjacent skill."""
    pool = expand_skills_for_pool(skills)
    placeholders = ",".join("?" for _ in pool)
    query = f"""
    SELECT e.employee_id, {EMPLOYEE_FULL_NAME_SQL_E} AS name, e.title, e.department, e.location,
           e.years_experience, e.current_utilization_pct, e.available_from, e.status,
           COALESCE(e.german_fluency, 'none') AS german_fluency
    FROM employees e
    JOIN employee_skills es ON e.employee_id = es.employee_id
    JOIN skills s ON es.skill_id = s.skill_id
    WHERE s.skill_name IN ({placeholders})
    GROUP BY e.employee_id
    HAVING COUNT(DISTINCT s.skill_name) >= 1
    """
    rows = conn.execute(query, pool).fetchall()
    return rows


def fetch_candidates_for_ranking(required_skills, location=None):
    """Return full candidate records (with employee_id) for scoring."""
    skills, _location = _split_skills_and_location(required_skills, location)
    if not skills and not _location:
        return []

    conn = get_staffing_conn()
    try:
        if skills:
            rows = _fetch_candidates_by_skills(conn, skills)
        else:
            rows = conn.execute(
                f"""
                SELECT {_EMPLOYEE_RANKING_SELECT}
                FROM employees
                WHERE location = ?
                """,
                (_location,),
            ).fetchall()

        return [_ranking_row(conn, row) for row in rows]
    finally:
        conn.close()


def search_people(required_skills, location=None):
    skills, _location = _split_skills_and_location(required_skills, location)
    if not skills and not _location:
        return []

    conn = get_staffing_conn()
    try:
        if skills:
            rows = _fetch_candidates_by_skills(conn, skills)
            return [_search_row_from_ranking_row(row) for row in rows]

        rows = conn.execute(
            f"""
            SELECT {EMPLOYEE_FULL_NAME_SQL} AS name, title, department, location, available_from
            FROM employees
            WHERE location = ?
            """,
            (_location,),
        ).fetchall()
        return [_employee_row(row) for row in rows]
    finally:
        conn.close()


def get_availability(required_availability):
    needle = (required_availability or "").strip()
    if not needle:
        return []

    conn = get_staffing_conn()
    try:
        if _DATE_RE.match(needle):
            query = f"""
            SELECT {EMPLOYEE_FULL_NAME_SQL} AS name, available_from, location
            FROM employees
            WHERE available_from <= ?
            ORDER BY available_from
            """
            rows = conn.execute(query, (needle,)).fetchall()
        else:
            query = f"""
            SELECT {EMPLOYEE_FULL_NAME_SQL} AS name, available_from, location
            FROM employees
            WHERE available_from LIKE ?
            ORDER BY available_from
            """
            rows = conn.execute(query, (f"%{needle}%",)).fetchall()

        return [
            {"name": row[0], "available_from": row[1], "location": row[2]}
            for row in rows
        ]
    finally:
        conn.close()


def check_project_history(employee_name):
    from data.project_history import fetch_project_history

    name = (employee_name or "").strip()
    if not name:
        return []

    conn = get_staffing_conn()
    try:
        rows = conn.execute(
            f"""
            SELECT employee_id, {EMPLOYEE_FULL_NAME_SQL} AS name, title, department, location,
                   years_experience, status, available_from
            FROM employees
            WHERE LOWER({EMPLOYEE_FULL_NAME_SQL}) = LOWER(?)
            """,
            (name,),
        ).fetchall()

        matches = []
        for row in rows:
            employee_id = row[0]
            skills = _fetch_skills_for_employee_by_name(conn, row[1])
            projects = fetch_project_history(employee_id)
            matches.append({
                "employee_id": employee_id,
                "name": row[1],
                "title": row[2],
                "department": row[3],
                "location": row[4],
                "years_experience": row[5],
                "status": row[6],
                "available_from": row[7],
                "skills": skills,
                "projects": projects,
            })

        return matches
    finally:
        conn.close()
