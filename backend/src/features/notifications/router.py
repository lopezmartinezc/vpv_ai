from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.notifications.config import vapid_settings
from src.features.notifications.schemas import PushSubscribeRequest, PushUnsubscribeRequest
from src.features.notifications.service import NotificationService
from src.shared.dependencies import get_current_user, get_db

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _get_service(db: AsyncSession = Depends(get_db)) -> NotificationService:
    return NotificationService(db)


@router.get("/vapid-public-key")
async def get_vapid_public_key() -> dict[str, str]:
    """Return the VAPID public key for push subscription."""
    return {"public_key": vapid_settings.vapid_public_key}


@router.post("/subscribe")
async def subscribe(
    body: PushSubscribeRequest,
    user: dict = Depends(get_current_user),
    service: NotificationService = Depends(_get_service),
) -> dict[str, bool]:
    """Register a push subscription for the current user."""
    await service.subscribe(
        user_id=int(user["sub"]),
        endpoint=body.endpoint,
        p256dh=body.p256dh,
        auth=body.auth,
    )
    return {"subscribed": True}


@router.post("/unsubscribe")
async def unsubscribe(
    body: PushUnsubscribeRequest,
    _user: dict = Depends(get_current_user),
    service: NotificationService = Depends(_get_service),
) -> dict[str, bool]:
    """Remove a push subscription."""
    deleted = await service.unsubscribe(body.endpoint)
    return {"unsubscribed": deleted}
