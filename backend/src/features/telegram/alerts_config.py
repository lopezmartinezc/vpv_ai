"""Per-season toggles for Telegram alert events.

The admin can opt out of individual event types from
``/admin/temporadas`` (writes to ``seasons.alerts_config``).
This module is the single source of truth for the *event
identifiers* and the default-on behavior.

Default-on rationale: pre-existing seasons have no
``alerts_config`` row → the helper treats every event as
enabled, preserving the historic behavior of sending every
alert.
"""

from __future__ import annotations

from typing import Final

# All event keys understood by the alerts_config gate. Frontend uses
# the same keys; keep both in sync. Add a new entry, gate the emit
# site, expose a checkbox — that's it.
EVENT_DEADLINE_REMINDER: Final[str] = "deadline_reminder"
EVENT_LINEUP_SUBMITTED: Final[str] = "lineup_submitted"
EVENT_LIVE_MATCH_EVENTS: Final[str] = "live_match_events"

ALERT_EVENTS: Final[tuple[str, ...]] = (
    EVENT_DEADLINE_REMINDER,
    EVENT_LINEUP_SUBMITTED,
    EVENT_LIVE_MATCH_EVENTS,
)


def is_alert_event_enabled(alerts_config: dict | None, event: str) -> bool:
    """Return True when *event* should fire a Telegram alert.

    Treats the absence of the config — NULL column, missing
    ``events`` key, or missing per-event key — as "enabled" so
    seasons created before this feature shipped behave as they did.
    """
    if not alerts_config:
        return True
    events = alerts_config.get("events")
    if not isinstance(events, dict):
        return True
    value = events.get(event)
    if value is None:
        return True
    return bool(value)
