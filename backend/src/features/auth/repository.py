from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.shared.models.invite import Invite
from src.shared.models.user import User


class AuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_user_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: int) -> User | None:
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_password_hash(self, user_id: int, password_hash: str) -> None:
        stmt = update(User).where(User.id == user_id).values(password_hash=password_hash)
        await self.session.execute(stmt)

    async def create_user(
        self,
        username: str,
        password_hash: str,
        display_name: str,
    ) -> User:
        user = User(
            username=username,
            password_hash=password_hash,
            display_name=display_name,
            is_admin=False,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def get_users_without_password(self) -> list[User]:
        stmt = select(User).where(User.password_hash == "").order_by(User.display_name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_all_users(self) -> list[User]:
        stmt = select(User).order_by(User.display_name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def toggle_admin(self, user_id: int) -> User | None:
        user = await self.get_user_by_id(user_id)
        if user is None:
            return None
        stmt = update(User).where(User.id == user_id).values(is_admin=not user.is_admin)
        await self.session.execute(stmt)
        user.is_admin = not user.is_admin
        return user


class InviteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        created_by_id: int,
        target_user_id: int | None,
        expires_days: int,
    ) -> Invite:
        invite = Invite(
            token=secrets.token_urlsafe(32),
            target_user_id=target_user_id,
            created_by_id=created_by_id,
            expires_at=datetime.utcnow() + timedelta(days=expires_days),
        )
        self.session.add(invite)
        await self.session.flush()
        return invite

    async def get_valid_by_token(self, token: str) -> Invite | None:
        stmt = (
            select(Invite)
            .options(
                joinedload(Invite.target_user),
                joinedload(Invite.created_by),
            )
            .where(
                Invite.token == token,
                Invite.used_at.is_(None),
                Invite.expires_at > datetime.utcnow(),
            )
        )
        result = await self.session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def mark_used(self, invite_id: int, used_by_id: int) -> None:
        stmt = (
            update(Invite)
            .where(Invite.id == invite_id)
            .values(used_at=datetime.utcnow(), used_by_id=used_by_id)
        )
        await self.session.execute(stmt)

    async def list_all(self, limit: int = 50) -> list[Invite]:
        stmt = (
            select(Invite)
            .options(
                joinedload(Invite.target_user),
                joinedload(Invite.created_by),
            )
            .order_by(Invite.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.unique().scalars().all())
