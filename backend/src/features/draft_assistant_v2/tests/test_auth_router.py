from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI
from fastapi.security import HTTPAuthorizationCredentials

from src.shared.models.user import User

from .. import auth, history, router
from ..config import config
from ..errors import AssistantError
from ..schemas import History


@pytest.mark.asyncio
async def test_missing_and_malformed_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(AssistantError) as error:
        await auth.admin_id(None)
    assert error.value.status == 401
    monkeypatch.setattr(auth, "decode_token", lambda token: {"sub": "bad"})
    with pytest.raises(AssistantError) as error:
        await auth.admin_id(HTTPAuthorizationCredentials(scheme="Bearer", credentials="token"))
    assert error.value.code == "INVALID_SESSION"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "admin,session_id,status",
    [(True, "valid", 200), (False, "valid", 403), (True, "revoked", 401)],
)
async def test_current_database_role_and_session(
    monkeypatch: pytest.MonkeyPatch, admin: bool, session_id: str, status: int
) -> None:
    user = User(id=11, is_admin=admin, session_id=session_id)
    session = MagicMock()
    session.get = AsyncMock(return_value=user)
    session.execute = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    monkeypatch.setattr(auth, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(
        auth, "decode_token", lambda token: {"sub": "11", "session_id": "valid", "is_admin": True}
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="token")
    if status == 200:
        assert await auth.admin_id(credentials) == 11
    else:
        with pytest.raises(AssistantError) as error:
            await auth.admin_id(credentials)
        assert error.value.status == status


@pytest.mark.asyncio
async def test_private_history_and_disabled_route(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    app.include_router(router.router)
    app.add_exception_handler(AssistantError, router.exception_handler)  # type: ignore[arg-type]

    async def authorized() -> int:
        return 11

    app.dependency_overrides[auth.admin_id] = authorized
    read = AsyncMock(return_value=History())
    monkeypatch.setattr(history, "read_history", read)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.get("/draft-assistant-v2/1/history")
        assert result.status_code == 200
        read.assert_awaited_once_with(11, 1)
        monkeypatch.setattr(config, "enabled", False)
        result = await client.get("/draft-assistant-v2/1/history")
        assert result.status_code == 503 and result.json()["code"] == "V2_DISABLED"
        app.dependency_overrides.clear()
        result = await client.get("/draft-assistant-v2/1/history")
        assert result.status_code == 401
