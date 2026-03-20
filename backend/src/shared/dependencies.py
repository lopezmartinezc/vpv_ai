from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.exceptions import AuthenticationError, AuthorizationError
from src.shared.permissions import Perm

if TYPE_CHECKING:
    from collections.abc import Callable

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


def require_perm(*perms: Perm) -> Callable:
    """Factory that creates a FastAPI dependency requiring specific permissions.

    Admin (is_admin=True) always passes. Otherwise checks bitmap.
    """

    async def checker(user: dict = Depends(get_current_user)) -> dict:
        if user.get("is_admin"):
            return user
        user_perms = user.get("permissions", 0)
        if not any(user_perms & p for p in perms):
            raise AuthorizationError("Permisos insuficientes")
        return user

    return checker


__all__ = [
    "get_current_admin",
    "get_current_user",
    "get_db",
    "require_perm",
]
