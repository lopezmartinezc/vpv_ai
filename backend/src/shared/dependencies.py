from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.exceptions import AuthenticationError, AuthorizationError

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if credentials is None:
        raise AuthenticationError("Token de autenticacion requerido")
    from src.features.auth.service import decode_token

    payload = decode_token(credentials.credentials)

    # Validate session_id against DB (single session enforcement)
    session_id = payload.get("session_id")
    if session_id:
        from src.shared.models.user import User

        user = await db.get(User, int(payload["sub"]))
        if user is None:
            raise AuthenticationError("Usuario no encontrado")
        if user.session_id != session_id:
            raise AuthenticationError("Sesion invalidada. Inicia sesion de nuevo.")

    return payload


async def get_current_admin(
    user: dict = Depends(get_current_user),
) -> dict:
    if not user.get("is_admin"):
        raise AuthorizationError("Se requieren permisos de administrador")
    return user


async def get_draft_manager(
    user: dict = Depends(get_current_user),
) -> dict:
    if not user.get("is_admin") and not user.get("is_draft_manager"):
        raise AuthorizationError("Se requieren permisos de gestor de draft")
    return user


__all__ = ["get_current_admin", "get_current_user", "get_db", "get_draft_manager"]
