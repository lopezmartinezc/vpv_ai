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

# Top-level events. Frontend uses the same keys; keep both in sync.
# `live_match_events` (singular) is the LEGACY master switch from the
# first iteration; once we shipped per-subtype toggles it became
# a kill-switch that disables every live subtype at once.
EVENT_DEADLINE_REMINDER: Final[str] = "deadline_reminder"
EVENT_LINEUP_SUBMITTED: Final[str] = "lineup_submitted"
EVENT_LIVE_MATCH_EVENTS: Final[str] = "live_match_events"  # legacy kill-switch

ALERT_EVENTS: Final[tuple[str, ...]] = (
    EVENT_DEADLINE_REMINDER,
    EVENT_LINEUP_SUBMITTED,
)

# Per-subtype gates for the live-events feed. Keys mirror the
# `event_type` strings emitted by live_events.parse — never rename
# without touching both.
LIVE_EVENT_PREFIX: Final[str] = "live_match."

LIVE_EVENT_TYPES: Final[tuple[str, ...]] = (
    "goal",
    "assist",
    "yellow",
    "red",
    "sub_in",
    "sub_out",
    "penalty_committed",
    "woodwork",
    "error_garrafal",
    "last_man_tackle",
)


def _events_dict(alerts_config: dict | None) -> dict | None:
    if not alerts_config:
        return None
    events = alerts_config.get("events")
    return events if isinstance(events, dict) else None


def is_alert_event_enabled(alerts_config: dict | None, event: str) -> bool:
    """Return True when *event* should fire a Telegram alert.

    Treats the absence of the config — NULL column, missing
    ``events`` key, or missing per-event key — as "enabled" so
    seasons created before this feature shipped behave as they did.
    """
    events = _events_dict(alerts_config)
    if events is None:
        return True
    value = events.get(event)
    if value is None:
        return True
    return bool(value)


def is_live_event_enabled(alerts_config: dict | None, event_type: str) -> bool:
    """Return True when a live-match event of *event_type* should fire.

    Resolution order:
    1. Legacy kill-switch ``live_match_events: false`` disables every
       subtype (back-compat with the first iteration of this UI).
    2. Per-subtype key ``live_match.{event_type}``: missing or true
       enables, false disables.
    """
    events = _events_dict(alerts_config)
    if events is None:
        return True
    if events.get(EVENT_LIVE_MATCH_EVENTS) is False:
        return False
    key = f"{LIVE_EVENT_PREFIX}{event_type}"
    value = events.get(key)
    if value is None:
        return True
    return bool(value)
