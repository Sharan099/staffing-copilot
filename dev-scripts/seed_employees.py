"""
Seed script for staffing_bosch_style.db (expanded, realistic version)

Models a real OEM/Tier-1 supplier internal staffing & bench-management system:
  employees          -> core HR + resourcing record
  skills              -> master skill list
  employee_skills     -> skill + proficiency + years used
  certifications      -> professional certs (ISO 26262, AWS, PMP, Scrum, ...)
  clients             -> external clients / internal business units
  projects            -> engagements (internal or client-billable)
  project_allocations -> who is staffed where, at what %, active/planned/ended
  bench_periods       -> bench history with reason and duration

Run from project root:

    .\\.venv\\Scripts\\python.exe dev-scripts/seed_employees.py
"""

import random
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

from faker import Faker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC = PROJECT_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from data.db import STAFFING_DB_PATH

fake = Faker("de_DE")
Faker.seed(42)
random.seed(42)

TODAY = date(2026, 7, 6)  # fixed "as of" date so the dataset is reproducible

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

GERMAN_FLUENCY_LEVELS = ["none", "A1", "A2", "B1", "B2", "C1", "C2", "native"]
GERMAN_FLUENCY_WEIGHTS = [5, 8, 10, 20, 25, 15, 10, 7]

ENGLISH_FLUENCY_LEVELS = ["B1", "B2", "C1", "C2", "native"]
ENGLISH_FLUENCY_WEIGHTS = [5, 20, 40, 25, 10]

DEPARTMENTS = [
    "Cross-Domain Computing Solutions",
    "Mobility Electronics",
    "Power Solutions",
    "ETAS - Software & Cybersecurity",
    "Vehicle Motion",
    "Connected Mobility Solutions",
    "Chassis Systems Control",
]
LOCATIONS = [
    ("Stuttgart", "Germany"), ("Munich", "Germany"), ("Leipzig", "Germany"),
    ("Dingolfing", "Germany"), ("Berlin", "Germany"), ("Renningen", "Germany"),
    ("Budapest", "Hungary"), ("Cluj-Napoca", "Romania"), ("Bengaluru", "India"),
]
TITLES_BY_LEVEL = {
    "Junior": ["Junior Software Engineer", "Junior ML Engineer", "Associate Engineer"],
    "Mid": ["Software Engineer", "ML Engineer", "Embedded Systems Engineer",
            "Platform Engineer", "DevOps Engineer", "Functional Safety Engineer"],
    "Senior": ["Senior Software Engineer", "Senior ML Engineer", "AI Engineer",
               "Senior Embedded Systems Engineer", "Technical Lead"],
    "Lead": ["Lead Engineer", "Engineering Manager", "Principal Engineer"],
}
SENIORITY_BY_YEARS = [
    (0, 2, "Junior"), (2, 6, "Mid"), (6, 11, "Senior"), (11, 100, "Lead"),
]
EMPLOYMENT_TYPES = ["Permanent", "Permanent", "Permanent", "Contractor", "Working Student"]

SKILL_POOL = [
    ("Python", "Programming"), ("C++", "Programming"), ("Embedded C", "Programming"),
    ("Go", "Programming"), ("Rust", "Programming"),
    ("AUTOSAR", "Automotive"), ("CAN Bus", "Automotive"), ("ISO 26262", "Automotive"),
    ("ROS", "Automotive"),
    ("LLM", "AI/ML"), ("RAG", "AI/ML"), ("LangGraph", "AI/ML"), ("TensorFlow", "AI/ML"),
    ("PyTorch", "AI/ML"), ("Computer Vision", "AI/ML"), ("MLOps", "AI/ML"),
    ("Kubernetes", "Infrastructure"), ("FastAPI", "Infrastructure"), ("Docker", "Infrastructure"),
    ("Terraform", "Infrastructure"), ("AWS", "Infrastructure"), ("Azure", "Infrastructure"),
]

CERT_POOL = [
    ("ISO 26262 Functional Safety Engineer", "TÜV SÜD", 3),
    ("AWS Certified Solutions Architect", "Amazon Web Services", 3),
    ("Certified Scrum Master", "Scrum Alliance", 2),
    ("PMP", "PMI", 3),
    ("Automotive SPICE Provisional Assessor", "intacs", 3),
    ("TensorFlow Developer Certificate", "Google", 3),
    ("Azure AI Engineer Associate", "Microsoft", 2),
    ("CKA - Certified Kubernetes Administrator", "CNCF", 3),
]

CLIENTS = [
    ("BMW Group", "Automotive OEM"),
    ("Mercedes-Benz AG", "Automotive OEM"),
    ("Volkswagen AG", "Automotive OEM"),
    ("Stellantis", "Automotive OEM"),
    ("Internal - Corporate Research", "Internal"),
    ("Internal - Platform Engineering", "Internal"),
    ("Rivian", "Automotive OEM"),
    ("Scania", "Commercial Vehicles"),
]

PROJECT_NAME_TEMPLATES = [
    "{client} - ADAS Perception Stack",
    "{client} - Battery Management Software",
    "{client} - Cybersecurity Hardening Program",
    "{client} - Infotainment Platform Migration",
    "{client} - Predictive Maintenance ML Pipeline",
    "{client} - Vehicle Motion Control Refactor",
    "{client} - Cloud Backend Modernization",
    "{client} - AUTOSAR Adaptive Rollout",
    "{client} - LLM Copilot for Diagnostics",
    "{client} - E/E Architecture Simulation Tooling",
]
PROJECT_ROLES = [
    "Software Engineer", "Technical Lead", "ML Engineer", "DevOps Engineer",
    "Functional Safety Reviewer", "Solution Architect", "QA Engineer",
]
BENCH_REASONS = [
    "Project ended - awaiting new assignment",
    "Ramp-down due to client budget cut",
    "New joiner - onboarding period",
    "Returned from parental leave",
    "Notice period - internal transfer pending",
    "Skill re-alignment / upskilling",
]

NUM_EMPLOYEES = 800
NUM_PROJECTS = 120


def rand_date(start: date, end: date) -> date:
    delta = (end - start).days
    if delta <= 0:
        return start
    return start + timedelta(days=random.randint(0, delta))


def seniority_for_years(years: int) -> str:
    for lo, hi, level in SENIORITY_BY_YEARS:
        if lo <= years < hi:
            return level
    return "Lead"


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA = """
DROP TABLE IF EXISTS bench_periods;
DROP TABLE IF EXISTS project_allocations;
DROP TABLE IF EXISTS projects;
DROP TABLE IF EXISTS clients;
DROP TABLE IF EXISTS certifications;
DROP TABLE IF EXISTS employee_skills;
DROP TABLE IF EXISTS skills;
DROP TABLE IF EXISTS employees;

CREATE TABLE employees (
    employee_id INTEGER PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT UNIQUE,
    title TEXT,
    seniority_level TEXT,
    department TEXT,
    location TEXT,
    country TEXT,
    manager_id INTEGER REFERENCES employees(employee_id),
    cost_center TEXT,
    employment_type TEXT,
    hire_date TEXT,
    years_experience INTEGER,
    german_fluency TEXT DEFAULT 'none',
    english_fluency TEXT DEFAULT 'B2',
    status TEXT,                     -- billable | bench | leave | notice_period
    current_utilization_pct INTEGER,  -- derived from active allocations
    available_from TEXT,              -- next date with free capacity
    last_performance_rating TEXT      -- Exceeds | Meets | Below (last cycle)
);

CREATE TABLE skills (
    skill_id INTEGER PRIMARY KEY,
    skill_name TEXT UNIQUE NOT NULL,
    category TEXT
);

CREATE TABLE employee_skills (
    employee_id INTEGER REFERENCES employees(employee_id),
    skill_id INTEGER REFERENCES skills(skill_id),
    proficiency_level TEXT,   -- Beginner | Intermediate | Advanced | Expert
    years_used INTEGER,
    PRIMARY KEY (employee_id, skill_id)
);

CREATE TABLE certifications (
    cert_id INTEGER PRIMARY KEY,
    employee_id INTEGER REFERENCES employees(employee_id),
    cert_name TEXT,
    issuing_body TEXT,
    issued_date TEXT,
    expiry_date TEXT
);

CREATE TABLE clients (
    client_id INTEGER PRIMARY KEY,
    client_name TEXT UNIQUE,
    client_type TEXT   -- Automotive OEM | Commercial Vehicles | Internal
);

CREATE TABLE projects (
    project_id INTEGER PRIMARY KEY,
    project_name TEXT,
    client_id INTEGER REFERENCES clients(client_id),
    project_type TEXT,     -- client_billable | internal
    delivery_model TEXT,   -- onsite | hybrid | remote
    location TEXT,
    start_date TEXT,
    end_date TEXT,          -- NULL if ongoing / open-ended
    status TEXT             -- planned | active | closed
);

CREATE TABLE project_allocations (
    allocation_id INTEGER PRIMARY KEY,
    employee_id INTEGER REFERENCES employees(employee_id),
    project_id INTEGER REFERENCES projects(project_id),
    role_on_project TEXT,
    allocation_pct INTEGER,
    start_date TEXT,
    end_date TEXT,
    status TEXT   -- planned | active | completed
);

CREATE TABLE bench_periods (
    bench_id INTEGER PRIMARY KEY,
    employee_id INTEGER REFERENCES employees(employee_id),
    bench_start_date TEXT,
    bench_end_date TEXT,   -- NULL if still on bench
    reason TEXT
);

CREATE INDEX idx_skill_name ON skills(skill_name);
CREATE INDEX idx_employee_skills_emp ON employee_skills(employee_id);
CREATE INDEX idx_allocations_emp ON project_allocations(employee_id);
CREATE INDEX idx_allocations_proj ON project_allocations(project_id);
"""


def seed_database():
    conn = sqlite3.connect(STAFFING_DB_PATH)
    conn.executescript(SCHEMA)

    # ---------------- skills ----------------
    conn.executemany(
        "INSERT INTO skills (skill_name, category) VALUES (?,?)", SKILL_POOL
    )
    skill_lookup = {
        name: sid for sid, name in conn.execute("SELECT skill_id, skill_name FROM skills")
    }

    # ---------------- clients ----------------
    conn.executemany(
        "INSERT INTO clients (client_name, client_type) VALUES (?,?)", CLIENTS
    )
    client_rows = list(conn.execute("SELECT client_id, client_name, client_type FROM clients"))

    # ---------------- projects ----------------
    project_rows = []
    for pid in range(1, NUM_PROJECTS + 1):
        client_id, client_name, client_type = random.choice(client_rows)
        project_type = "internal" if client_type == "Internal" else "client_billable"
        name = random.choice(PROJECT_NAME_TEMPLATES).format(client=client_name.split(" -")[0])
        start = rand_date(date(2023, 1, 1), date(2026, 5, 1))
        # ~70% of projects have a planned end date; rest open-ended
        end = None
        if random.random() < 0.7:
            end = start + timedelta(days=random.randint(120, 730))
        if end and end < TODAY:
            status = "closed"
        elif start > TODAY:
            status = "planned"
        else:
            status = "active"
        location, country = random.choice(LOCATIONS)
        delivery_model = random.choice(["onsite", "hybrid", "remote"])
        conn.execute(
            "INSERT INTO projects VALUES (?,?,?,?,?,?,?,?,?)",
            (pid, name, client_id, project_type, delivery_model, location,
             start.isoformat(), end.isoformat() if end else None, status),
        )
        project_rows.append((pid, start, end, status))

    active_or_planned_projects = [p for p in project_rows if p[3] in ("active", "planned")]

    # ---------------- employees ----------------
    manager_pool = []  # employee_ids eligible to be managers (Senior/Lead)
    employees = []

    for emp_id in range(1, NUM_EMPLOYEES + 1):
        first_name = fake.first_name()
        last_name = fake.last_name()
        years = int(random.triangular(0, 20, 6))
        seniority = seniority_for_years(years)
        title = random.choice(TITLES_BY_LEVEL[seniority])
        department = random.choice(DEPARTMENTS)
        location, country = random.choice(LOCATIONS)
        hire_date = TODAY - timedelta(days=int(years * 365.25) + random.randint(0, 300))
        employment_type = random.choice(EMPLOYMENT_TYPES) if seniority != "Lead" else "Permanent"
        german = random.choices(GERMAN_FLUENCY_LEVELS, weights=GERMAN_FLUENCY_WEIGHTS, k=1)[0]
        english = random.choices(ENGLISH_FLUENCY_LEVELS, weights=ENGLISH_FLUENCY_WEIGHTS, k=1)[0]
        manager_id = random.choice(manager_pool) if manager_pool and random.random() < 0.9 else None
        cost_center = f"CC-{department[:3].upper()}-{random.randint(100,199)}"
        email = f"{first_name.lower()}.{last_name.lower()}{emp_id}@bosch.com".replace(" ", "")
        rating = random.choices(
            ["Exceeds", "Meets", "Below", "Not yet rated"], weights=[15, 60, 10, 15], k=1
        )[0]

        employees.append({
            "id": emp_id, "first_name": first_name, "last_name": last_name,
            "email": email, "title": title, "seniority": seniority,
            "department": department, "location": location, "country": country,
            "manager_id": manager_id, "cost_center": cost_center,
            "employment_type": employment_type, "hire_date": hire_date,
            "years_experience": years, "german": german, "english": english,
            "rating": rating,
        })
        if seniority in ("Senior", "Lead"):
            manager_pool.append(emp_id)

    # ---------------- allocations + bench + derived status ----------------
    allocation_id = 1
    bench_id = 1

    for emp in employees:
        emp_id = emp["id"]
        num_allocations = random.choices([0, 1, 2], weights=[20, 55, 25], k=1)[0]
        total_pct = 0
        chosen_projects = random.sample(
            active_or_planned_projects, k=min(num_allocations, len(active_or_planned_projects))
        ) if num_allocations else []

        for proj_id, p_start, p_end, p_status in chosen_projects:
            remaining = 100 - total_pct
            if remaining <= 0:
                break
            pct = random.choice([20, 30, 40, 50, 60, 80, 100])
            pct = min(pct, remaining)
            alloc_status = "planned" if p_status == "planned" else "active"
            alloc_start = max(p_start, emp["hire_date"])
            alloc_end = p_end  # may be None (open-ended)
            conn.execute(
                "INSERT INTO project_allocations VALUES (?,?,?,?,?,?,?,?)",
                (allocation_id, emp_id, proj_id, random.choice(PROJECT_ROLES), pct,
                 alloc_start.isoformat(), alloc_end.isoformat() if alloc_end else None,
                 alloc_status),
            )
            allocation_id += 1
            total_pct += pct

        if total_pct == 0:
            status = "bench"
            available_from = TODAY.isoformat()
            bench_start = TODAY - timedelta(days=random.randint(1, 90))
            conn.execute(
                "INSERT INTO bench_periods VALUES (?,?,?,?,?)",
                (bench_id, emp_id, bench_start.isoformat(), None,
                 random.choice(BENCH_REASONS)),
            )
            bench_id += 1
        elif total_pct < 100:
            status = "billable"
            available_from = (TODAY + timedelta(days=random.randint(10, 60))).isoformat()
        else:
            status = "billable"
            available_from = (TODAY + timedelta(days=random.randint(60, 240))).isoformat()

        # small chance of leave / notice period overriding
        if random.random() < 0.03:
            status = "leave"
        elif random.random() < 0.02:
            status = "notice_period"

        conn.execute(
            "INSERT INTO employees VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                emp["id"], emp["first_name"], emp["last_name"], emp["email"],
                emp["title"], emp["seniority"], emp["department"], emp["location"],
                emp["country"], emp["manager_id"], emp["cost_center"],
                emp["employment_type"], emp["hire_date"].isoformat(),
                emp["years_experience"], emp["german"], emp["english"],
                status, total_pct, available_from, emp["rating"],
            ),
        )

        # ---------------- skills ----------------
        num_skills = random.randint(2, 6)
        for skill_name, _ in random.sample(SKILL_POOL, num_skills):
            proficiency = random.choices(
                ["Beginner", "Intermediate", "Advanced", "Expert"],
                weights=[20, 35, 30, 15], k=1,
            )[0]
            years_used = min(emp["years_experience"], random.randint(1, 10))
            conn.execute(
                "INSERT INTO employee_skills VALUES (?,?,?,?)",
                (emp_id, skill_lookup[skill_name], proficiency, years_used),
            )

        # ---------------- certifications ----------------
        if random.random() < 0.4:
            for cert_name, issuer, valid_years in random.sample(
                CERT_POOL, k=random.randint(1, 2)
            ):
                issued = rand_date(emp["hire_date"], TODAY)
                expiry = issued + timedelta(days=365 * valid_years)
                conn.execute(
                    "INSERT INTO certifications (employee_id, cert_name, issuing_body, "
                    "issued_date, expiry_date) VALUES (?,?,?,?,?)",
                    (emp_id, cert_name, issuer, issued.isoformat(), expiry.isoformat()),
                )

    conn.commit()

    counts = {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ["employees", "skills", "employee_skills", "certifications",
                       "clients", "projects", "project_allocations", "bench_periods"]
    }
    conn.close()
    print(f"Seeded {STAFFING_DB_PATH}")
    for table, n in counts.items():
        print(f"  {table:22s}: {n}")


if __name__ == "__main__":
    seed_database()