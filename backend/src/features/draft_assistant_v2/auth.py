from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, ValidationError

from src.core.database import AsyncSessionLocal
from src.core.exceptions import AuthenticationError
from src.features.auth.service import decode_token
from src.shared.models.user import User

from .errors import AssistantError
from .history import configure

bearer = HTTPBearer(auto_error=False)


class Claims(BaseModel):
    sub: str = Field(pattern=r"^[1-9][0-9]*$")
    session_id: str = Field(min_length=1)


async def admin_id(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> int:
    if credentials is None:
        raise AssistantError("AUTH_REQUIRED", "Inicia sesión como administrador.", 401)
    try:
        claims = Claims.model_validate(decode_token(credentials.credentials))
    except (ValidationError, AuthenticationError) as exc:
        raise AssistantError("INVALID_SESSION", "Sesión no válida.", 401) from exc
    async with AsyncSessionLocal() as session, session.begin():
        await configure(session)
        user = await session.get(User, int(claims.sub))
        if user is None or user.session_id != claims.session_id:
            raise AssistantError("INVALID_SESSION", "Sesión no válida.", 401)
        if not user.is_admin:
            raise AssistantError("ADMIN_REQUIRED", "Se requieren permisos de administrador.", 403)
        return user.id
