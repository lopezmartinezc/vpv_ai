"""Tests for the per-season alert-event gate.

The helper has to be conservative: a missing config or a missing
event key both mean the historic behavior, "always send", so that
seasons created before this feature shipped keep working.
"""

from __future__ import annotations

from src.features.telegram.alerts_config import (
    EVENT_DEADLINE_REMINDER,
    EVENT_LINEUP_SUBMITTED,
    EVENT_LIVE_MATCH_EVENTS,
    LIVE_EVENT_PREFIX,
    LIVE_EVENT_TYPES,
    is_alert_event_enabled,
    is_live_event_enabled,
)


class TestDefaultsAreEnabled:
    """Historic behavior: no config row => every alert fires."""

    def test_none_config_enables_all_events(self) -> None:
        assert is_alert_event_enabled(None, EVENT_DEADLINE_REMINDER) is True
        assert is_alert_event_enabled(None, EVENT_LINEUP_SUBMITTED) is True

    def test_empty_config_enables_all_events(self) -> None:
        assert is_alert_event_enabled({}, EVENT_DEADLINE_REMINDER) is True

    def test_missing_events_key_enables_all(self) -> None:
        assert is_alert_event_enabled({"other": 1}, EVENT_LINEUP_SUBMITTED) is True

    def test_events_not_a_dict_falls_back_to_enabled(self) -> None:
        # Defensive: if someone hand-edits the JSONB to an invalid shape,
        # don't silence alerts — fail open.
        assert is_alert_event_enabled({"events": "yes"}, EVENT_DEADLINE_REMINDER) is True
        assert is_alert_event_enabled({"events": [1, 2]}, EVENT_DEADLINE_REMINDER) is True


class TestExplicitToggles:
    def test_explicit_true_enables(self) -> None:
        cfg = {"events": {EVENT_DEADLINE_REMINDER: True}}
        assert is_alert_event_enabled(cfg, EVENT_DEADLINE_REMINDER) is True

    def test_explicit_false_disables(self) -> None:
        cfg = {"events": {EVENT_LINEUP_SUBMITTED: False}}
        assert is_alert_event_enabled(cfg, EVENT_LINEUP_SUBMITTED) is False

    def test_one_disabled_does_not_affect_others(self) -> None:
        cfg = {"events": {EVENT_DEADLINE_REMINDER: False}}
        assert is_alert_event_enabled(cfg, EVENT_DEADLINE_REMINDER) is False
        # Anything not in the dict stays enabled.
        assert is_alert_event_enabled(cfg, EVENT_LINEUP_SUBMITTED) is True
        assert is_alert_event_enabled(cfg, EVENT_LIVE_MATCH_EVENTS) is True

    def test_truthy_non_bool_values_enabled(self) -> None:
        # Defensive coercion — admin might POST 1 instead of true.
        cfg = {"events": {EVENT_DEADLINE_REMINDER: 1}}
        assert is_alert_event_enabled(cfg, EVENT_DEADLINE_REMINDER) is True

    def test_falsy_non_bool_values_disabled(self) -> None:
        cfg = {"events": {EVENT_LINEUP_SUBMITTED: 0}}
        assert is_alert_event_enabled(cfg, EVENT_LINEUP_SUBMITTED) is False


class TestLiveEventGate:
    """Per-subtype filter for live-match events (goal, yellow, ...)."""

    def test_defaults_to_enabled_for_every_subtype(self) -> None:
        for subtype in LIVE_EVENT_TYPES:
            assert is_live_event_enabled(None, subtype) is True
            assert is_live_event_enabled({}, subtype) is True

    def test_explicit_subtype_false_disables_only_that_one(self) -> None:
        cfg = {"events": {f"{LIVE_EVENT_PREFIX}yellow": False}}
        assert is_live_event_enabled(cfg, "yellow") is False
        assert is_live_event_enabled(cfg, "red") is True
        assert is_live_event_enabled(cfg, "goal") is True

    def test_legacy_kill_switch_disables_every_subtype(self) -> None:
        # The first iteration of the UI had a single live_match_events
        # boolean. We honor it as a kill switch so old configs keep
        # working — disables every subtype regardless of finer keys.
        cfg = {"events": {EVENT_LIVE_MATCH_EVENTS: False}}
        for subtype in LIVE_EVENT_TYPES:
            assert is_live_event_enabled(cfg, subtype) is False

    def test_legacy_kill_switch_true_yields_to_per_subtype_keys(self) -> None:
        cfg = {
            "events": {
                EVENT_LIVE_MATCH_EVENTS: True,
                f"{LIVE_EVENT_PREFIX}sub_in": False,
            }
        }
        assert is_live_event_enabled(cfg, "sub_in") is False
        assert is_live_event_enabled(cfg, "goal") is True

    def test_unknown_event_type_defaults_to_enabled(self) -> None:
        # Defensive: if futbolfantasy adds a new icon and our event_type
        # map gets richer, the gate should fail open instead of silently
        # blocking the new subtype.
        assert is_live_event_enabled({"events": {}}, "var_review") is True
