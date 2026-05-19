from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    SeasonLockedError,
)
from src.shared.permissions import Perm

logger = logging.getLogger(__name__)

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


async def _check_season_writable(season_id: int, user: dict, db: AsyncSession) -> dict:
    """Shared logic: raise SeasonLockedError if season is finished + locked."""
    from src.shared.models.season import Season

    season = await db.get(Season, season_id)
    if season is None:
        raise NotFoundError("Season", season_id)
    if season.status != "finished":
        return user
    if not user.get("is_admin"):
        raise SeasonLockedError()
    if not season.edit_unlocked:
        raise SeasonLockedError()
    logger.warning(
        "season_writable: ADMIN OVERRIDE on finished season %d by user %s",
        season_id,
        user.get("sub"),
    )
    return user


async def require_season_writable(
    season_id: int,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Block mutations on finished seasons unless admin has unlocked edits.

    Reads ``season_id`` from path. See ``_check_season_writable`` for rules.
    """
    return await _check_season_writable(season_id, user, db)


async def require_draft_writable(
    draft_id: int,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Same as ``require_season_writable`` but resolves season via draft_id."""
    from src.shared.models.draft import Draft

    draft = await db.get(Draft, draft_id)
    if draft is None:
        raise NotFoundError("Draft", draft_id)
    return await _check_season_writable(draft.season_id, user, db)


__all__ = [
    "get_current_admin",
    "get_current_user",
    "get_db",
    "require_draft_writable",
    "require_perm",
    "require_season_writable",
]
