"""Model Settings API — per-manager LLM provider credentials."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from api.auth import check_auth, require_manager
from api.config import get_zdr_status
from api.llm_providers import list_providers_payload
from data.manager_credentials import get_credentials_masked, save_credentials

router = APIRouter(prefix="/api/settings", tags=["settings"])

LLM_DATA_FLOW = {
    "workflow": [
        "Manager submits a staffing request (natural language).",
        "Backend extracts search criteria via LLM (no employee PII sent).",
        "Candidates are ranked locally using the internal database and scoring engine.",
        "Optional LLM summaries use minimized candidate records (candidate#ID only).",
        "Full names and emails are resolved in the backend after the LLM responds.",
        "Every outbound LLM payload is redacted and logged in llm_request_log.",
    ],
    "sent_to_llm": {
        "extract_request": [
            "Manager staffing request text (may mention skills, location, dates)",
            "Known location list (system prompt)",
        ],
        "search_summary": [
            "Staffing request text",
            "Search criteria (skills, location, needed_by)",
            "Per candidate: candidate_id, title, location, experience, availability, scores, judgment flags",
        ],
        "fit_summary": [
            "Staffing request text",
            "Per candidate: candidate_id, title, department, location, skills, scores, judgment flags",
            "Minimized staffing memory (counts/labels, no names)",
        ],
    },
    "never_sent_to_llm": [
        "Email addresses",
        "Full name (replaced with candidate#ID)",
        "Salary, cost center, performance ratings",
        "Home address or personal contact details",
        "Full HR profile or certification details",
        "Manager API keys (used only in Authorization header to provider)",
    ],
}


@router.get("/compliance")
def get_compliance_status(authorization: str = Header(default=None)):
    check_auth(authorization)
    return {
        "zdr": get_zdr_status(),
        "data_flow": LLM_DATA_FLOW,
    }


class SaveCredentialsRequest(BaseModel):
    provider: str = Field(..., pattern="^(anthropic|groq)$")
    model_name: str = Field(..., min_length=1, max_length=120)
    api_key: str = Field(..., min_length=8, max_length=500)


@router.get("/providers")
def get_providers(authorization: str = Header(default=None)):
    check_auth(authorization)
    return list_providers_payload()


@router.get("/credentials")
def get_credentials(authorization: str = Header(default=None)):
    payload = check_auth(authorization)
    require_manager(payload)
    manager_id = payload["username"]
    saved = get_credentials_masked(manager_id)
    if saved is None:
        return {"configured": False}
    return saved


@router.post("/credentials")
def post_credentials(
    request: SaveCredentialsRequest,
    authorization: str = Header(default=None),
):
    payload = check_auth(authorization)
    require_manager(payload)
    manager_id = payload["username"]
    try:
        return save_credentials(
            manager_id,
            request.provider,
            request.model_name,
            request.api_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
