"""Unified LLM calls using each manager's saved provider, model, and API key."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from anthropic import Anthropic
from fastapi import HTTPException

from api.config import get_anthropic_timeout
from data.llm_audit import log_llm_request
from data.manager_credentials import get_credentials_for_call

logger = logging.getLogger(__name__)

_CREDENTIALS_MSG = (
    "AI credentials not configured. Open Model Settings and add your provider API key."
)


def ensure_manager_credentials(manager_id: str) -> dict:
    creds = get_credentials_for_call(manager_id)
    if creds is None:
        raise HTTPException(status_code=428, detail=_CREDENTIALS_MSG)
    return creds


def call_model_for_manager(
    manager_id: str,
    *,
    system: str | None = None,
    messages: list[dict],
    max_tokens: int = 1000,
    endpoint: str = "unknown",
    referenced_candidate_ids: list[int] | None = None,
) -> str:
    """Look up manager credentials, decrypt key in-memory, call the right provider."""
    creds = ensure_manager_credentials(manager_id)
    provider = creds["provider"]
    model = creds["model_name"]
    api_key = creds["api_key"]

    log_llm_request(
        manager_id=manager_id,
        endpoint=endpoint,
        provider=provider,
        system=system,
        messages=messages,
        model=model,
        max_tokens=max_tokens,
        referenced_candidate_ids=referenced_candidate_ids,
    )

    try:
        if provider == "anthropic":
            return _call_anthropic(api_key, model, system, messages, max_tokens)
        if provider == "groq":
            return _call_groq(api_key, model, system, messages, max_tokens)
        raise HTTPException(status_code=500, detail=f"Unknown provider: {provider}")
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("LLM call failed for manager=%s provider=%s: %s", manager_id, provider, exc)
        raise HTTPException(
            status_code=502,
            detail="AI provider request failed. Check your API key and model in Model Settings.",
        ) from exc
    finally:
        del api_key


def _call_anthropic(
    api_key: str,
    model: str,
    system: str | None,
    messages: list[dict],
    max_tokens: int,
) -> str:
    client = Anthropic(api_key=api_key)
    timeout = get_anthropic_timeout()
    kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if system:
        kwargs["system"] = system

    last_error = None
    for attempt in range(2):
        try:
            response = client.messages.create(**kwargs, timeout=timeout)
            text_blocks = [block.text for block in response.content if block.type == "text"]
            return text_blocks[0] if text_blocks else ""
        except Exception as exc:
            last_error = exc
            logger.warning("Anthropic API call failed (attempt %s/2)", attempt + 1)
    raise last_error


def _call_groq(
    api_key: str,
    model: str,
    system: str | None,
    messages: list[dict],
    max_tokens: int,
) -> str:
    payload_messages: list[dict] = []
    if system:
        payload_messages.append({"role": "system", "content": system})
    payload_messages.extend(messages)

    body = json.dumps({
        "model": model,
        "messages": payload_messages,
        "max_tokens": max_tokens,
    }).encode("utf-8")

    # Groq sits behind Cloudflare — urllib's default User-Agent (Python-urllib/*)
    # triggers 403 error code 1010. Send a normal client signature instead.
    request = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "StaffingCopilot/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=get_anthropic_timeout()) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        logger.warning("Groq API HTTP %s: %s", exc.code, err_body[:300])
        detail = _groq_error_detail(exc.code, err_body)
        raise HTTPException(status_code=502, detail=detail) from exc

    choices = data.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return message.get("content") or ""


def _groq_error_detail(status_code: int, err_body: str) -> str:
    try:
        payload = json.loads(err_body)
        message = payload.get("error", {}).get("message")
        if message:
            return f"Groq API error: {message}"
    except json.JSONDecodeError:
        pass
    if status_code == 401:
        return "Groq API key is invalid. Update it in Model Settings."
    if status_code == 403 and "1010" in err_body:
        return "Groq blocked the server request. Retry after saving credentials again."
    return "AI provider request failed. Check your API key and model in Model Settings."
