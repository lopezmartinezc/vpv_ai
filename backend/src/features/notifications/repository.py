from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models.push_subscription import PushSubscription


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_subscription(
        self, user_id: int, endpoint: str, p256dh: str, auth: str
    ) -> PushSubscription:
        """Create or update a push subscription by endpoint."""
        stmt = select(PushSubscription).where(PushSubscription.endpoint == endpoint)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is not None:
            existing.user_id = user_id
            existing.p256dh = p256dh
            existing.auth = auth
            return existing

        sub = PushSubscription(user_id=user_id, endpoint=endpoint, p256dh=p256dh, auth=auth)
        self.session.add(sub)
        await self.session.flush()
        return sub

    async def delete_by_endpoint(self, endpoint: str) -> bool:
        stmt = delete(PushSubscription).where(PushSubscription.endpoint == endpoint)
        cursor = await self.session.execute(stmt)
        return (getattr(cursor, "rowcount", 0) or 0) > 0

    async def get_subscriptions_for_users(self, user_ids: list[int]) -> list[PushSubscription]:
        if not user_ids:
            return []
        stmt = select(PushSubscription).where(PushSubscription.user_id.in_(user_ids))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
