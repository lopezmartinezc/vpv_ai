from __future__ import annotations

from fastapi import Request
from slowapi import Limiter

DEFAULT_LIMIT = "60/minute"


def _get_real_ip(request: Request) -> str:
    """Extract client IP, respecting X-Real-IP / X-Forwarded-For from Nginx."""
    forwarded = request.headers.get("X-Real-IP") or request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


limiter = Limiter(key_func=_get_real_ip, default_limits=[DEFAULT_LIMIT])
