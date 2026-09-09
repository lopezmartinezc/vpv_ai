"""The assistant endpoint must stay unlimited.

A cap that trips mid-pick is worse than the spend it prevents: during a draft
the admin asks as often as he needs to. The money guard belongs on the provider
console, not in a decorator that fails at the worst moment.

This is a structural check rather than a flood of requests, because the auth
dependency resolves before the limiter would ever run — a loop of unauthenticated
calls would prove nothing.
"""

from __future__ import annotations

from src.core.rate_limit import limiter
from src.features.draft_assistant import router as assistant_router


def test_ask_endpoint_has_no_slowapi_limit() -> None:
    # Importing the module registers any decorator-applied limits.
    qualified = f"{assistant_router.ask.__module__}.{assistant_router.ask.__qualname__}"
    assert qualified not in limiter._route_limits


def test_no_global_default_would_apply_either() -> None:
    """Default limits only bite when SlowAPIMiddleware is installed.

    The app registers the limiter state and the exception handler but no
    middleware, so an undecorated route is genuinely uncapped. If someone adds
    SlowAPIMiddleware later, this fails and the assistant needs an explicit
    exemption.
    """
    from slowapi.middleware import SlowAPIMiddleware

    from src.app import create_app

    app = create_app()
    assert not any(m.cls is SlowAPIMiddleware for m in app.user_middleware)
