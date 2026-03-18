from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.notifications.config import vapid_settings
from src.features.notifications.schemas import PushSubscribeRequest, PushUnsubscribeRequest
from src.features.notifications.service import NotificationService
from src.shared.dependencies import get_current_admin, get_current_user, get_db

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


@router.post("/admin/test-push")
async def test_push(
    _admin: dict = Depends(get_current_admin),
    service: NotificationService = Depends(_get_service),
) -> dict:
    """Send a test push notification to the admin user."""
    user_id = int(_admin["sub"])
    sent = await service.send_push_to_users(
        user_ids=[user_id],
        title="Test Liga VPV",
        body="Las notificaciones push funcionan correctamente",
        url="/",
    )
    return {"sent": sent}


@router.post("/admin/test-reminder")
async def test_reminder(
    _admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Force-send a deadline reminder to Telegram + Push (ignores time windows)."""
    from src.features.lineups.repository import LineupRepository
    from src.features.scraping.repository import ScrapingRepository
    from src.shared.models.user import User

    scraping_repo = ScrapingRepository(db)
    lineup_repo = LineupRepository(db)

    season = await scraping_repo.get_active_season()
    if season is None:
        return {"error": "No active season"}

    md_number = season.matchday_current
    if md_number == 0:
        return {"error": "matchday_current is 0"}

    matchday = await lineup_repo.get_matchday(season.id, md_number)
    if matchday is None:
        return {"error": f"Matchday {md_number} not found"}

    missing = await lineup_repo.get_participants_without_lineup(season.id, matchday.id)
    if not missing:
        return {"message": "Todos han enviado alineacion", "missing": 0}

    # Get display names
    from sqlalchemy import select

    user_ids = [p.user_id for p in missing]
    stmt = select(User.id, User.display_name).where(User.id.in_(user_ids))
    result = await db.execute(stmt)
    user_names = {row.id: row.display_name for row in result.all()}
    names = [user_names.get(p.user_id, "?") for p in missing]

    # Send Telegram
    telegram_sent = False
    try:
        from src.features.telegram.service import TelegramNotifier

        notifier = TelegramNotifier(db)
        message = f"\u23f0 TEST — Deadline J{md_number}\nSin alineacion: {', '.join(names)}"
        await notifier.send_alert(message)
        telegram_sent = True
    except Exception as exc:
        telegram_sent = False
        return {"error": f"Telegram failed: {exc}"}

    # Send Push
    push_sent = 0
    try:
        notification_service = NotificationService(db)
        push_sent = await notification_service.send_push_to_users(
            user_ids=user_ids,
            title=f"Deadline J{md_number}",
            body="Recordatorio: envia tu alineacion",
            url=f"/jornadas/{md_number}/alineacion",
        )
    except Exception:
        pass

    return {
        "missing": len(missing),
        "names": names,
        "telegram_sent": telegram_sent,
        "push_sent": push_sent,
    }
