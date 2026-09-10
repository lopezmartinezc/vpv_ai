"""The output budget has to leave room for a reasoning model to think.

In the OpenAI Responses API, `max_output_tokens` covers reasoning tokens AND
the visible answer. gpt-5 spends the former before emitting the latter, so a
budget sized for prose is spent entirely on thinking and the turn comes back
truncated with nothing in it — which the engine reads as "incomplete" and
throws the whole answer away.

That is what production returned on the first real V2 question: "Análisis
incompleto", no text at all, on gpt-5.
"""

from ..config import AssistantSettings


def test_the_budget_leaves_room_for_reasoning_plus_an_answer() -> None:
    # A detailed comparison runs to a few thousand tokens of prose on its own,
    # and a reasoning model can spend as much again before it starts writing.
    assert AssistantSettings().max_output_tokens >= 6000


def test_the_ceiling_can_absorb_a_harder_question() -> None:
    """A ceiling at the default means the next truncation cannot be fixed with
    an env var — which is what happened here: the cap was 4000."""
    bound = AssistantSettings.model_fields["max_output_tokens"].metadata
    ceiling = next(m.le for m in bound if hasattr(m, "le"))
    assert ceiling >= 4 * AssistantSettings().max_output_tokens
