"""Anthropic client helpers with timeout and retry."""

from __future__ import annotations

import logging

from anthropic import Anthropic

from api.config import get_anthropic_timeout

logger = logging.getLogger(__name__)


def create_anthropic_client() -> Anthropic:
    return Anthropic()


def call_anthropic(client: Anthropic, **kwargs):
    timeout = get_anthropic_timeout()
    last_error = None
    for attempt in range(2):
        try:
            return client.messages.create(**kwargs, timeout=timeout)
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Anthropic API call failed (attempt %s/2): %s",
                attempt + 1,
                exc,
            )
    raise last_error
