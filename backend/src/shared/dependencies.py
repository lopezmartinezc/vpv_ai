from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.core.database import get_db
from src.core.exceptions import AuthenticationError, AuthorizationError

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    if credentials is None:
        raise AuthenticationError("Token de autenticacion requerido")
    from src.features.auth.service import decode_token

    return decode_token(credentials.credentials)


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
