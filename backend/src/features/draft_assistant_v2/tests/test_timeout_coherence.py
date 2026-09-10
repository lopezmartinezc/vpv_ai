"""A single provider call cannot be allowed to outlast the whole question.

The total was capped at 170s to stay under the browser's 190s abort, but the
per-call ceiling stayed at 180 - a configuration where one call may run
longer than the budget that contains it, which can only end as a timeout with
nothing to show.
"""

import pytest
from pydantic import ValidationError

from ..config import AssistantSettings


def test_a_call_may_not_be_allowed_to_outlast_the_total() -> None:
    fields = AssistantSettings.model_fields
    ceiling = {
        name: next(m.le for m in fields[name].metadata if hasattr(m, "le"))
        for name in ("timeout_seconds", "provider_timeout_seconds")
    }
    assert ceiling["provider_timeout_seconds"] <= ceiling["timeout_seconds"]


def test_the_defaults_leave_room_for_more_than_one_call() -> None:
    config = AssistantSettings()
    assert config.timeout_seconds >= 2 * config.provider_timeout_seconds - 30


@pytest.mark.parametrize("seconds", [171, 190, 300])
def test_a_total_the_browser_would_abort_is_refused(seconds: int) -> None:
    with pytest.raises(ValidationError):
        AssistantSettings(timeout_seconds=seconds)
