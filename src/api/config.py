"""Application settings loaded from environment variables."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

_REQUIRED_ENV = "JWT_SECRET"
_MASTER_KEY_ENV = "MASTER_KEY"


def get_jwt_secret() -> str:
    secret = os.environ.get(_REQUIRED_ENV, "").strip()
    if not secret and "unittest" in sys.modules:
        return "unittest-only-jwt-secret-not-for-production"
    if not secret:
        raise RuntimeError(
            f"{_REQUIRED_ENV} environment variable is required. "
            "Copy .env.example to .env and set a long random value."
        )
    return secret


def get_master_key() -> bytes:
    """32-byte AES-256 key from MASTER_KEY env (64 hex chars). Never stored in DB."""
    raw = os.environ.get(_MASTER_KEY_ENV, "").strip()
    if not raw and "unittest" in sys.modules:
        return bytes.fromhex("aa" * 32)
    if not raw:
        raise RuntimeError(
            f"{_MASTER_KEY_ENV} environment variable is required. "
            "Generate with: openssl rand -hex 32"
        )
    try:
        key = bytes.fromhex(raw)
    except ValueError as exc:
        raise RuntimeError(f"{_MASTER_KEY_ENV} must be 64 hex characters (32 bytes)") from exc
    if len(key) != 32:
        raise RuntimeError(f"{_MASTER_KEY_ENV} must decode to exactly 32 bytes")
    return key


def get_cors_origins() -> list[str]:
    raw = os.environ.get(
        "CORS_ORIGINS",
        "http://127.0.0.1:5500,http://localhost:5500,"
        "http://127.0.0.1:8000,http://localhost:8000,null",
    )
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    if "null" in origins:
        origins = [o if o != "null" else "null" for o in origins]
    if not origins:
        raise RuntimeError("CORS_ORIGINS must list at least one allowed origin")
    return origins


def get_anthropic_timeout() -> float:
    return float(os.environ.get("ANTHROPIC_API_TIMEOUT_SECONDS", "60"))


def get_rate_limit_max() -> int:
    return int(os.environ.get("RATE_LIMIT_MAX_REQUESTS", "20"))


def get_rate_limit_window() -> int:
    return int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "60"))


def _env_flag_true(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def get_zdr_status() -> dict:
    """
    Zero Data Retention must be enabled manually in each provider console.
    These env flags record admin confirmation — they cannot be verified via API.
    """
    anthropic = _env_flag_true("ANTHROPIC_ZDR_CONFIRMED")
    groq = _env_flag_true("GROQ_ZDR_CONFIRMED")
    return {
        "anthropic_zdr_confirmed": anthropic,
        "groq_zdr_confirmed": groq,
        "all_confirmed": anthropic and groq,
        "verification_note": (
            "ZDR cannot be verified via API. "
            "Anthropic: contact sales/account team to enable ZDR per organization "
            "(not a self-serve console toggle). "
            "Groq: enable in GroqCloud Console → Data Controls."
        ),
        "anthropic_zdr_how_to": (
            "Request Zero Data Retention from Anthropic sales or your account representative. "
            "It is enabled per organization after review — there is no dashboard toggle for most API accounts. "
            "Docs: platform.claude.com/docs/en/manage-claude/api-and-data-retention"
        ),
        "groq_zdr_how_to": (
            "Organization admins can enable Zero Data Retention in GroqCloud → Data Controls. "
            "Docs: console.groq.com/docs/your-data"
        ),
    }
