from __future__ import annotations

import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.features.notifications.config import vapid_settings
from src.features.notifications.repository import NotificationRepository

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = NotificationRepository(session)

    async def subscribe(self, user_id: int, endpoint: str, p256dh: str, auth: str) -> bool:
        await self.repo.upsert_subscription(user_id, endpoint, p256dh, auth)
        return True

    async def unsubscribe(self, endpoint: str) -> bool:
        return await self.repo.delete_by_endpoint(endpoint)

    async def send_push_to_users(
        self, user_ids: list[int], title: str, body: str, url: str = "/"
    ) -> int:
        """Send push notification to all subscriptions for the given users.

        Returns the number of notifications successfully sent.
        """
        if not vapid_settings.vapid_private_key:
            logger.debug("send_push_to_users: VAPID keys not configured, skipping")
            return 0

        subs = await self.repo.get_subscriptions_for_users(user_ids)
        if not subs:
            return 0

        from pywebpush import WebPushException, webpush

        payload = json.dumps({"title": title, "body": body, "url": url})
        sent = 0

        for sub in subs:
            subscription_info = {
                "endpoint": sub.endpoint,
                "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
            }
            try:
                webpush(
                    subscription_info=subscription_info,
                    data=payload,
                    vapid_private_key=vapid_settings.vapid_private_key,
                    vapid_claims={"sub": vapid_settings.vapid_subject},
                )
                sent += 1
            except WebPushException as exc:
                # 410 Gone = subscription expired, clean up
                if (
                    hasattr(exc, "response")
                    and exc.response is not None
                    and exc.response.status_code == 410
                ):
                    await self.repo.delete_by_endpoint(sub.endpoint)
                    logger.info("push: removed expired subscription %s", sub.endpoint[:50])
                    continue
                logger.warning("push: failed for user_id=%d: %s", sub.user_id, exc)
            except Exception as exc:
                logger.warning("push: unexpected error for user_id=%d: %s", sub.user_id, exc)

        logger.info("send_push_to_users: sent %d/%d notifications", sent, len(subs))
        return sent
