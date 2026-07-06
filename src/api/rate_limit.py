"""Simple in-memory per-user rate limiting for expensive endpoints."""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException

from api.config import get_rate_limit_max, get_rate_limit_window

_request_times: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(username: str) -> None:
    now = time.time()
    window = get_rate_limit_window()
    max_requests = get_rate_limit_max()
    cutoff = now - window

    recent = [timestamp for timestamp in _request_times[username] if timestamp > cutoff]
    if len(recent) >= max_requests:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Try again shortly.",
        )

    recent.append(now)
    _request_times[username] = recent
