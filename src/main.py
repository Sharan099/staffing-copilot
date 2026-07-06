"""
Run from project root (uses the project venv):

    copy .env.example to .env and set JWT_SECRET and MASTER_KEY (openssl rand -hex 32)
    .\\.venv\\Scripts\\python.exe -m uvicorn main:app --reload --port 8000 --app-dir src

Production: terminate TLS at your reverse proxy (HTTPS only).
"""

import json
import logging
import datetime
import time

import bcrypt
import jwt
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import Response, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Literal

from pydantic import BaseModel, Field

from api.auth import JWT_SECRET, check_auth, require_manager
from api.config import get_cors_origins, get_zdr_status
from api.criteria import extract_criteria, extract_request_for_form
from api.gdpr import gdpr_delete_candidate
from api.llm_client import call_model_for_manager, ensure_manager_credentials
from api.llm_data_minimization import (
    build_fit_summary_prompt,
    minimize_ranked_for_llm,
    resolve_candidate_labels,
)
from api.rate_limit import check_rate_limit
from api.employee_profile import get_employee_profile
from api.report_pdf import build_report_pdf
from api.search_config import criteria_to_dict, merge_search_config
from api.settings import router as settings_router
from data.db import get_known_skills, get_reports_conn, get_staffing_conn, get_users_conn
from data.db import EMPLOYEE_FULL_NAME_SQL
from data.staffing_memory import log_rejection
from scoring.judgment import (
    enrich_ranked_candidates,
)
from scoring.scorer import ScoreCriteria, rank_candidates
from scoring.weights import DEFAULT_SCORING_WEIGHTS
from tool_runner import run_tool_call
from tools.tools import fetch_candidates_for_ranking

logger = logging.getLogger(__name__)

users_conn = get_users_conn()

app = FastAPI()
app.include_router(settings_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.on_event("startup")
def _check_zdr_on_startup():
    zdr = get_zdr_status()
    if not zdr["all_confirmed"]:
        logger.warning(
            "Zero Data Retention not confirmed for all LLM providers. "
            "Anthropic ZDR requires sales/account enablement (not a console toggle). "
            "Groq ZDR: GroqCloud Data Controls. "
            "Set ANTHROPIC_ZDR_CONFIRMED / GROQ_ZDR_CONFIRMED in .env after confirmation. "
            "See docs/DATA_PROCESSING.md."
        )


class LoginRequest(BaseModel):
    username: str
    password: str


class ScoringWeightsModel(BaseModel):
    skills: float = Field(default=40, ge=0, le=100)
    availability: float = Field(default=25, ge=0, le=100)
    experience: float = Field(default=15, ge=0, le=100)
    location: float = Field(default=10, ge=0, le=100)
    utilization: float = Field(default=10, ge=0, le=100)
    language: float = Field(default=0, ge=0, le=100)


class SearchConfigModel(BaseModel):
    required_skills: list[str] | None = None
    core_skills: list[str] | None = None
    location: str | None = None
    needed_by: str | None = None
    scoring_weights: ScoringWeightsModel | None = None
    client_facing: bool | None = None
    required_german_level: str | None = None


class ExtractRequestBody(BaseModel):
    client_message: str = Field(..., max_length=1000)


class AgentSearchRequest(BaseModel):
    client_message: str = Field(..., max_length=1000)
    model: str = "claude-sonnet-4-6"
    search_config: SearchConfigModel | None = None


class ApproveRequest(BaseModel):
    employee_id: int
    client_message: str = Field(..., max_length=1000)
    manager_notes: str = Field(default="", max_length=2000)
    search_config: SearchConfigModel | None = None
    works_council_notification: Literal["yes", "no", "unsure", "already_notified"]


class RejectRequest(BaseModel):
    employee_id: int
    client_message: str = Field(..., max_length=1000)
    manager_notes: str = Field(default="", max_length=2000)


@app.post("/login")
def login(request: LoginRequest):
    row = users_conn.execute(
        "SELECT password_hash, role FROM users WHERE username = ?",
        (request.username,),
    ).fetchone()

    if row is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    stored_hash, role = row
    if not bcrypt.checkpw(request.password.encode(), stored_hash.encode()):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    payload = {
        "username": request.username,
        "role": role,
        "exp": datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=8),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    return {"token": token}


def _server_ranked_top_five(criteria: ScoreCriteria) -> list[dict]:
    candidates = fetch_candidates_for_ranking(criteria.required_skills, criteria.location)
    return rank_candidates(candidates, criteria, top_n=5)


def generate_fit_summary(
    scored: dict,
    criteria: ScoreCriteria,
    client_message: str,
    manager_id: str,
) -> str:
    text = call_model_for_manager(
        manager_id,
        system=(
            "You write professional staffing fit summaries for internal reports. "
            "Refer to candidates only as candidate#ID (e.g. candidate#42). "
            "Explain why this employee is the right fit using ONLY the facts and scores "
            "provided. Two short paragraphs: (1) role fit, (2) availability and experience. "
            "If judgment flags or staffing memory are provided, weave them into your "
            "reasoning — especially burnout risk, prior rejections, or domain track record. "
            "Do not invent skills, dates, or project history."
        ),
        messages=[{
            "role": "user",
            "content": build_fit_summary_prompt(scored, criteria, client_message),
        }],
        max_tokens=500,
        endpoint="fit_summary",
        referenced_candidate_ids=[scored["employee_id"]],
    )
    if not text:
        return "Approved based on computed match score."
    return resolve_candidate_labels(text, {scored["employee_id"]: scored["name"]})


def generate_search_summary(
    ranked: list[dict],
    criteria: ScoreCriteria,
    client_message: str,
    manager_id: str,
) -> str:
    if not ranked:
        return "No employees matched the requirement. Try broadening skills or location."

    slim_ranked = minimize_ranked_for_llm(ranked)
    candidate_ids = [c["employee_id"] for c in ranked]
    text = call_model_for_manager(
        manager_id,
        system=(
            "Summarize ranked staffing candidates for a manager. "
            "Refer to candidates only as candidate#ID. "
            "Use ONLY the candidate data provided. Mention the top recommendation "
            "and briefly note alternatives. When judgment flags exist (burnout risk, "
            "repeat domain pattern, prior rejection, domain track record), surface them "
            "in plain language — managers need operational judgment, not just scores. "
            "Professional, concise."
        ),
        messages=[{
            "role": "user",
            "content": (
                f"Request: {client_message}\n"
                f"Criteria: skills={criteria.required_skills}, "
                f"location={criteria.location}, needed_by={criteria.needed_by}\n"
                f"Ranked candidates: {json.dumps(slim_ranked)}"
            ),
        }],
        max_tokens=400,
        endpoint="search_summary",
        referenced_candidate_ids=candidate_ids,
    )
    name_by_id = {c["employee_id"]: c["name"] for c in ranked}
    if not text:
        return f"Top recommendation: {ranked[0]['name']}."
    return resolve_candidate_labels(text, name_by_id)


def _compute_meta(ranked: list[dict], elapsed_ms: float) -> dict:
    top_score = ranked[0]["total_score"] if ranked else 0
    max_observed = 100.0
    confidence = min(0.99, round(top_score / max_observed, 2)) if ranked else 0
    return {
        "execution_time_ms": round(elapsed_ms, 1),
        "tools_used": [
            "extract_criteria",
            "search_people",
            "rank_scorer",
            "project_history",
            "staffing_memory",
            "judgment_layer",
            "generate_summary",
        ],
        "documents_retrieved": len(ranked),
        "confidence": confidence,
        "reasoning_score": min(100, int(top_score * 100 / max_observed)) if ranked else 0,
    }


def _resolve_criteria(
    client_message: str,
    manager_id: str,
    search_config: SearchConfigModel | None,
) -> ScoreCriteria:
    extracted = extract_criteria(client_message, manager_id)
    config_dict = search_config.model_dump(exclude_none=True) if search_config else None
    return merge_search_config(extracted, config_dict)


def run_agent_search_streaming(
    manager_id: str,
    client_message: str,
    search_config: SearchConfigModel | None = None,
):
    started = time.time()

    def step(step_id: str, label: str, status: str, chip: str = "blue"):
        return json.dumps({
            "type": "step",
            "id": step_id,
            "label": label,
            "status": status,
            "chip": chip,
        }) + "\n"

    yield step("auth", "Authenticating manager", "completed", "green")

    try:
        ensure_manager_credentials(manager_id)
    except HTTPException as exc:
        yield json.dumps({"type": "error", "message": exc.detail}) + "\n"
        return

    yield step("understand", "Understanding requirements", "running", "blue")

    try:
        criteria = _resolve_criteria(client_message, manager_id, search_config)
    except HTTPException as exc:
        yield step("understand", "Understanding requirements", "failed", "orange")
        yield json.dumps({"type": "error", "message": exc.detail}) + "\n"
        return
    except Exception:
        logger.exception("Criteria extraction failed")
        yield step("understand", "Understanding requirements", "failed", "orange")
        yield json.dumps({
            "type": "error",
            "message": "Could not parse the staffing requirement. Please try again.",
        }) + "\n"
        return

    yield step("understand", "Understanding requirements", "completed", "green")
    yield step("structure", "Creating structured request", "completed", "green")
    yield step("search", "Searching employee database", "running", "blue")

    class _FakeCall:
        def __init__(self, name, input_data):
            self.name = name
            self.input = input_data

    search_call = _FakeCall(
        "search_people",
        {"required_skills": criteria.required_skills, "location": criteria.location},
    )
    result, status, duration_ms = run_tool_call(search_call, caller_role="manager")

    yield step("search", "Searching employee database", "completed", "green")
    yield step("skills", "Filtering by skills", "completed", "green")
    yield step("availability", "Checking availability", "running", "blue")
    yield step("availability", "Checking availability", "completed", "green")
    yield step("certs", "Checking certifications", "completed", "green")
    yield step("projects", "Evaluating previous projects", "completed", "blue")
    yield step("confidence", "Calculating confidence", "running", "blue")

    try:
        ranked = _server_ranked_top_five(criteria)
        ranked = enrich_ranked_candidates(ranked, client_message)
    except Exception:
        logger.exception("Candidate ranking failed")
        yield step("confidence", "Calculating confidence", "failed", "orange")
        yield json.dumps({
            "type": "error",
            "message": "Could not search the employee database. Please try again.",
        }) + "\n"
        return

    yield step("confidence", "Calculating confidence", "completed", "green")
    yield step("rank", "Ranking candidates", "completed", "green")
    yield step("explain", "Generating explanation", "running", "blue")

    try:
        summary = generate_search_summary(ranked, criteria, client_message, manager_id)
    except HTTPException as exc:
        yield step("explain", "Generating explanation", "failed", "orange")
        yield json.dumps({"type": "error", "message": exc.detail}) + "\n"
        return

    meta = _compute_meta(ranked, (time.time() - started) * 1000)

    yield step("explain", "Generating explanation", "completed", "green")

    yield json.dumps({
        "type": "criteria",
        "criteria": criteria_to_dict(criteria),
        "client_message": client_message,
    }) + "\n"

    yield json.dumps({
        "type": "candidates",
        "candidates": ranked,
        "summary": summary,
        "meta": meta,
    }) + "\n"

    yield json.dumps({"type": "meta", **meta}) + "\n"


def _criteria_from_message(
    client_message: str,
    manager_id: str,
    search_config: SearchConfigModel | None = None,
) -> ScoreCriteria:
    return _resolve_criteria(client_message, manager_id, search_config)


def _fetch_report_row(report_id: int) -> dict:
    reports_conn = get_reports_conn()
    row = reports_conn.execute(
        """
        SELECT id, employee_id, employee_name, approved_by, approved_at,
               required_skills, location, needed_by, total_score, score_breakdown,
               justification, manager_notes, client_message, employee_profile,
               works_council_notification
        FROM reports WHERE id = ?
        """,
        (report_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Report not found")

    keys = [
        "id", "employee_id", "employee_name", "approved_by", "approved_at",
        "required_skills", "location", "needed_by", "total_score", "score_breakdown",
        "justification", "manager_notes", "client_message", "employee_profile",
        "works_council_notification",
    ]
    return dict(zip(keys, row))


@app.post("/api/extract-request")
def extract_request(
    request: ExtractRequestBody,
    authorization: str = Header(default=None),
):
    payload = check_auth(authorization)
    require_manager(payload)
    check_rate_limit(payload["username"])
    ensure_manager_credentials(payload["username"])
    try:
        return extract_request_for_form(request.client_message, payload["username"])
    except HTTPException:
        raise
    except Exception:
        logger.exception("Request extraction failed")
        raise HTTPException(
            status_code=500,
            detail="Could not extract fields from your description. Please try again.",
        ) from None


@app.get("/search-options")
def search_options(authorization: str = Header(default=None)):
    check_auth(authorization)
    from data.db import KNOWN_LOCATIONS
    from scoring.german_fluency import GERMAN_FLUENCY_PICKER_LEVELS
    return {
        "skills": get_known_skills(),
        "locations": list(KNOWN_LOCATIONS),
        "german_fluency_levels": list(GERMAN_FLUENCY_PICKER_LEVELS),
        "default_scoring_weights": DEFAULT_SCORING_WEIGHTS.as_dict(),
    }


@app.post("/agent-search")
def agent_search(request: AgentSearchRequest, authorization: str = Header(default=None)):
    payload = check_auth(authorization)
    require_manager(payload)
    check_rate_limit(payload["username"])
    return StreamingResponse(
        run_agent_search_streaming(
            payload["username"],
            request.client_message,
            request.search_config,
        ),
        media_type="application/x-ndjson",
    )


@app.post("/approve")
def approve_candidate(
    request: ApproveRequest,
    authorization: str = Header(default=None),
):
    payload = check_auth(authorization)
    require_manager(payload)
    check_rate_limit(payload["username"])
    approved_by = payload["username"]
    ensure_manager_credentials(approved_by)

    criteria = _criteria_from_message(request.client_message, approved_by, request.search_config)
    ranked = enrich_ranked_candidates(
        _server_ranked_top_five(criteria),
        request.client_message,
    )
    scored = next(
        (candidate for candidate in ranked if candidate["employee_id"] == request.employee_id),
        None,
    )
    if scored is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Employee is not in the agent's top-ranked candidates for this search. "
                "Run a new agent search and approve a listed candidate."
            ),
        )

    fit_summary = generate_fit_summary(scored, criteria, request.client_message, approved_by)
    approved_at = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")

    employee_profile = {
        "title": scored.get("title"),
        "department": scored.get("department"),
        "location": scored.get("location"),
        "years_experience": scored.get("years_experience"),
        "available_from": scored.get("available_from"),
        "skills": scored.get("skills", []),
        "status": scored.get("status"),
        "german_fluency": scored.get("german_fluency"),
    }

    works_council = request.works_council_notification

    reports_conn = get_reports_conn()
    cursor = reports_conn.execute(
        """
        INSERT INTO reports (
            employee_id, employee_name, approved_by, approved_at,
            required_skills, location, needed_by,
            total_score, score_breakdown, justification,
            manager_notes, client_message, employee_profile,
            works_council_notification
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            scored["employee_id"],
            scored["name"],
            approved_by,
            approved_at,
            json.dumps(criteria.required_skills),
            criteria.location,
            criteria.needed_by,
            scored["total_score"],
            json.dumps(scored["score_breakdown"]),
            fit_summary,
            request.manager_notes.strip(),
            request.client_message,
            json.dumps(employee_profile),
            works_council,
        ),
    )
    reports_conn.commit()
    report_id = cursor.lastrowid

    report = _fetch_report_row(report_id)
    return {
        "report_id": report_id,
        "employee_id": scored["employee_id"],
        "employee_name": scored["name"],
        "employee_profile": employee_profile,
        "approved_by": approved_by,
        "approved_at": approved_at,
        "total_score": scored["total_score"],
        "score_breakdown": scored["score_breakdown"],
        "fit_summary": fit_summary,
        "manager_notes": request.manager_notes.strip(),
        "client_message": request.client_message,
        "criteria": criteria_to_dict(criteria),
        "works_council_notification": works_council,
        "pdf_url": f"/reports/{report_id}/pdf",
    }


@app.post("/reject")
def reject_candidate(
    request: RejectRequest,
    authorization: str = Header(default=None),
):
    payload = check_auth(authorization)
    require_manager(payload)
    check_rate_limit(payload["username"])

    staffing = get_staffing_conn()
    try:
        name_row = staffing.execute(
            f"SELECT {EMPLOYEE_FULL_NAME_SQL} AS name FROM employees WHERE employee_id = ?",
            (request.employee_id,),
        ).fetchone()
    finally:
        staffing.close()

    if name_row is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    employee_name = name_row[0]

    rejection_id = log_rejection(
        request.employee_id,
        employee_name,
        payload["username"],
        request.client_message,
        request.manager_notes.strip(),
    )
    return {
        "rejection_id": rejection_id,
        "employee_id": request.employee_id,
        "employee_name": employee_name,
        "rejected_by": payload["username"],
    }


@app.get("/reports")
def list_reports(authorization: str = Header(default=None)):
    check_auth(authorization)
    reports_conn = get_reports_conn()
    rows = reports_conn.execute(
        """
        SELECT id, employee_name, approved_by, approved_at, total_score
        FROM reports ORDER BY id DESC LIMIT 50
        """
    ).fetchall()
    return {
        "reports": [
            {
                "report_id": row[0],
                "employee_name": row[1],
                "approved_by": row[2],
                "approved_at": row[3],
                "total_score": row[4],
            }
            for row in rows
        ]
    }


@app.get("/reports/{report_id}")
def get_report(report_id: int, authorization: str = Header(default=None)):
    check_auth(authorization)
    report = _fetch_report_row(report_id)
    return {
        "report_id": report["id"],
        "employee_id": report["employee_id"],
        "employee_name": report["employee_name"],
        "approved_by": report["approved_by"],
        "approved_at": report["approved_at"],
        "total_score": report["total_score"],
        "score_breakdown": json.loads(report["score_breakdown"]),
        "fit_summary": report["justification"],
        "manager_notes": report.get("manager_notes") or "",
        "client_message": report.get("client_message") or "",
        "employee_profile": json.loads(report.get("employee_profile") or "{}"),
        "works_council_notification": report.get("works_council_notification") or "",
        "criteria": {
            "required_skills": json.loads(report["required_skills"]),
            "location": report.get("location"),
            "needed_by": report.get("needed_by"),
        },
        "pdf_url": f"/reports/{report_id}/pdf",
    }


@app.get("/api/employees/{employee_id}/profile")
def employee_profile(employee_id: int, authorization: str = Header(default=None)):
    check_auth(authorization)
    profile = get_employee_profile(employee_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return profile


@app.delete("/api/candidates/{candidate_id}/gdpr-delete")
def gdpr_delete_candidate_endpoint(
    candidate_id: int,
    authorization: str = Header(default=None),
):
    payload = check_auth(authorization)
    require_manager(payload)
    return gdpr_delete_candidate(candidate_id, performed_by=payload["username"])


@app.get("/reports/{report_id}/pdf")
def download_report_pdf(report_id: int, authorization: str = Header(default=None)):
    check_auth(authorization)
    report = _fetch_report_row(report_id)
    pdf_bytes = build_report_pdf(report)
    filename = f"staffing-report-{report_id}-{report['employee_name'].replace(' ', '-')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/")
def health():
    return {"status": "ok"}
