import os
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = Path(os.environ.get("STAFFING_DATA_DIR", PROJECT_ROOT))
STAFFING_DB_PATH = _DATA_DIR / "staffing_bosch_style.db"
USERS_DB_PATH = _DATA_DIR / "users.db"
REPORTS_DB_PATH = _DATA_DIR / "reports.db"

KNOWN_LOCATIONS = (
    "Stuttgart",
    "Munich",
    "Leipzig",
    "Dingolfing",
    "Berlin",
    "Renningen",
)

# employees table uses first_name + last_name (no single name column)
EMPLOYEE_FULL_NAME_SQL = "(first_name || ' ' || last_name)"
EMPLOYEE_FULL_NAME_SQL_E = "(e.first_name || ' ' || e.last_name)"


def get_known_skills() -> list[str]:
    conn = get_staffing_conn()
    try:
        rows = conn.execute(
            "SELECT skill_name FROM skills ORDER BY skill_name"
        ).fetchall()
        return [row[0] for row in rows]
    finally:
        conn.close()


def _backfill_german_fluency(conn: sqlite3.Connection) -> None:
    """Assign reproducible german_fluency values to employees."""
    import random as rnd

    rows = conn.execute("SELECT employee_id FROM employees").fetchall()
    levels = ["none", "A1", "A2", "B1", "B2", "C1", "C2", "native"]
    weights = [5, 8, 10, 20, 25, 15, 10, 7]
    for (employee_id,) in rows:
        level = rnd.Random(employee_id).choices(levels, weights=weights, k=1)[0]
        conn.execute(
            "UPDATE employees SET german_fluency = ? WHERE employee_id = ?",
            (level, employee_id),
        )


def _needs_german_backfill(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT COUNT(DISTINCT COALESCE(german_fluency, '')) FROM employees"
    ).fetchone()
    return (row[0] or 0) <= 1


def ensure_staffing_schema(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(employees)")}
    if "german_fluency" not in columns:
        conn.execute(
            "ALTER TABLE employees ADD COLUMN german_fluency TEXT DEFAULT 'none'"
        )
        conn.commit()
    if _needs_german_backfill(conn):
        _backfill_german_fluency(conn)
        conn.commit()

    from data.project_history import ensure_project_history_schema
    ensure_project_history_schema(conn)


def get_staffing_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(STAFFING_DB_PATH, check_same_thread=False)
    try:
        ensure_staffing_schema(conn)
    except sqlite3.OperationalError:
        pass
    return conn


def get_users_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(USERS_DB_PATH, check_same_thread=False)
    from data.manager_credentials import ensure_manager_credentials_schema
    ensure_manager_credentials_schema(conn)
    return conn


def get_reports_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(REPORTS_DB_PATH, check_same_thread=False)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL,
        employee_name TEXT NOT NULL,
        approved_by TEXT NOT NULL,
        approved_at TEXT NOT NULL,
        required_skills TEXT NOT NULL,
        location TEXT,
        needed_by TEXT,
        total_score REAL NOT NULL,
        score_breakdown TEXT NOT NULL,
        justification TEXT NOT NULL,
        manager_notes TEXT DEFAULT '',
        client_message TEXT DEFAULT '',
        employee_profile TEXT DEFAULT '{}'
    )
    """)
    existing = {row[1] for row in conn.execute("PRAGMA table_info(reports)")}
    migrations = {
        "manager_notes": "ALTER TABLE reports ADD COLUMN manager_notes TEXT DEFAULT ''",
        "client_message": "ALTER TABLE reports ADD COLUMN client_message TEXT DEFAULT ''",
        "employee_profile": "ALTER TABLE reports ADD COLUMN employee_profile TEXT DEFAULT '{}'",
        "works_council_notification": (
            "ALTER TABLE reports ADD COLUMN works_council_notification TEXT DEFAULT ''"
        ),
    }
    for column, statement in migrations.items():
        if column not in existing:
            conn.execute(statement)
    conn.commit()

    from data.staffing_memory import ensure_rejections_schema
    ensure_rejections_schema(conn)

    from data.llm_audit import ensure_llm_audit_schema
    ensure_llm_audit_schema(conn)

    return conn
