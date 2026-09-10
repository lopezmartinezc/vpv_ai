"""The tool budget has to survive the question people actually ask.

"¿A quién cojo en este pick?" is not one lookup. It legitimately chains the
board, the picks so far, who is still to choose, the rosters, the fixtures and
the season form — eight or more tool calls before the model has enough to
answer. V1 shipped with eight rounds, production answered "Me he quedado sin
vueltas consultando datos", and it was raised to twenty.

These tests exist so V2 cannot quietly reintroduce the same wall.
"""

from src.core.config import settings

from ..config import AssistantSettings


def test_the_round_budget_is_at_least_what_v1_needed() -> None:
    assert AssistantSettings().max_rounds >= settings.assistant_max_tool_rounds


def test_tool_calls_are_not_the_narrower_limit() -> None:
    """A generous round budget spent through a stingy call budget is the same
    wall wearing a different name."""
    config = AssistantSettings()
    assert config.max_tool_calls >= config.max_rounds


def test_the_ceiling_leaves_room_to_raise_it_further() -> None:
    """The field bound, not just the default: a cap at the default means the
    next production incident cannot be fixed with an env var."""
    bound = AssistantSettings.model_fields["max_rounds"].metadata
    ceiling = next(getattr(m, "le") for m in bound if hasattr(m, "le"))
    assert ceiling > AssistantSettings().max_rounds
