from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import AuthenticationError, AuthorizationError, BusinessRuleError
from src.features.auth.repository import AuthRepository, InviteRepository
from src.features.auth.schemas import (
    AdminUserResponse,
    InviteResponse,
    InviteStatusResponse,
    TokenResponse,
    UserResponse,
    UserWithoutPasswordResponse,
)
from src.shared.models.invite import Invite
from src.shared.models.user import User

def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _create_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "is_admin": user.is_admin,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise AuthenticationError("Token invalido o expirado") from exc


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        email=user.email,
        is_admin=user.is_admin,
    )


def _invite_response(invite: Invite) -> InviteResponse:
    return InviteResponse(
        id=invite.id,
        token=invite.token,
        target_user_id=invite.target_user_id,
        target_display_name=invite.target_user.display_name if invite.target_user else None,
        created_by_display_name=invite.created_by.display_name,
        expires_at=invite.expires_at,
        used_at=invite.used_at,
        created_at=invite.created_at,
    )


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.auth_repo = AuthRepository(session)
        self.invite_repo = InviteRepository(session)
        self.session = session

    async def login(self, username: str, password: str) -> TokenResponse:
        user = await self.auth_repo.get_user_by_username(username)
        if user is None or not _verify_password(password, user.password_hash):
            raise AuthenticationError("Usuario o contrasena incorrectos")
        return TokenResponse(access_token=_create_token(user))

    async def get_me(self, user_id: int) -> UserResponse:
        user = await self.auth_repo.get_user_by_id(user_id)
        if user is None:
            raise AuthenticationError("Usuario no encontrado")
        return _user_response(user)

    async def refresh(self, user_id: int) -> TokenResponse:
        user = await self.auth_repo.get_user_by_id(user_id)
        if user is None:
            raise AuthenticationError("Usuario no encontrado")
        return TokenResponse(access_token=_create_token(user))

    async def validate_invite(self, token: str) -> InviteStatusResponse:
        invite = await self.invite_repo.get_valid_by_token(token)
        if invite is None:
            return InviteStatusResponse(valid=False, expired=True)
        return InviteStatusResponse(
            valid=True,
            target_user_id=invite.target_user_id,
            target_display_name=invite.target_user.display_name if invite.target_user else None,
        )

    async def register_with_invite(
        self,
        token: str,
        password: str,
        username: str | None,
    ) -> TokenResponse:
        invite = await self.invite_repo.get_valid_by_token(token)
        if invite is None:
            raise BusinessRuleError("Invitacion invalida o expirada")

        hashed = _hash_password(password)

        if invite.target_user_id:
            # Existing user — just set password
            await self.auth_repo.update_password_hash(invite.target_user_id, hashed)
            user = await self.auth_repo.get_user_by_id(invite.target_user_id)
        else:
            # New user — create account
            if not username:
                raise BusinessRuleError("Se requiere nombre de usuario para nuevos registros")
            existing = await self.auth_repo.get_user_by_username(username)
            if existing:
                raise BusinessRuleError("Nombre de usuario ya existe")
            user = await self.auth_repo.create_user(
                username=username,
                password_hash=hashed,
                display_name=username,
            )

        await self.invite_repo.mark_used(invite.id, user.id)
        await self.session.commit()
        return TokenResponse(access_token=_create_token(user))

    async def create_invite(
        self,
        admin_id: int,
        target_user_id: int | None,
        expires_days: int,
    ) -> InviteResponse:
        if target_user_id:
            user = await self.auth_repo.get_user_by_id(target_user_id)
            if user is None:
                raise BusinessRuleError("Usuario destino no encontrado")
        invite = await self.invite_repo.create(admin_id, target_user_id, expires_days)
        await self.session.commit()
        # Reload with relationships
        loaded = await self.invite_repo.get_valid_by_token(invite.token)
        return _invite_response(loaded)

    async def list_invites(self) -> list[InviteResponse]:
        invites = await self.invite_repo.list_all()
        return [_invite_response(inv) for inv in invites]

    async def get_users_without_password(self) -> list[UserWithoutPasswordResponse]:
        users = await self.auth_repo.get_users_without_password()
        return [
            UserWithoutPasswordResponse(id=u.id, username=u.username, display_name=u.display_name)
            for u in users
        ]

    async def list_users(self) -> list[AdminUserResponse]:
        users = await self.auth_repo.get_all_users()
        return [
            AdminUserResponse(
                id=u.id,
                username=u.username,
                display_name=u.display_name,
                email=u.email,
                is_admin=u.is_admin,
                has_password=bool(u.password_hash),
                telegram_chat_id=u.telegram_chat_id,
            )
            for u in users
        ]

    async def toggle_admin(self, user_id: int, admin_id: int) -> AdminUserResponse:
        if user_id == admin_id:
            raise BusinessRuleError("No puedes quitarte admin a ti mismo")
        user = await self.auth_repo.toggle_admin(user_id)
        if user is None:
            raise BusinessRuleError("Usuario no encontrado")
        await self.session.commit()
        return AdminUserResponse(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            email=user.email,
            is_admin=user.is_admin,
            has_password=bool(user.password_hash),
            telegram_chat_id=user.telegram_chat_id,
        )

    async def reset_password(self, user_id: int, admin_id: int) -> InviteResponse:
        user = await self.auth_repo.get_user_by_id(user_id)
        if user is None:
            raise BusinessRuleError("Usuario no encontrado")
        invite = await self.invite_repo.create(admin_id, user_id, 7)
        await self.session.commit()
        loaded = await self.invite_repo.get_valid_by_token(invite.token)
        return _invite_response(loaded)
