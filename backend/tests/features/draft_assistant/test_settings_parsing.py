"""Settings arrive through systemd's EnvironmentFile, which is not dotenv.

systemd ignores comments only on their OWN line: ``KEY=value  # note`` hands the
comment over as part of the value. Left untreated that turns a correct-looking
.env into "ASSISTANT_PROVIDER no valido" — or, worse, a silently corrupted API
key — at the first question of a live draft.
"""

from __future__ import annotations

from src.features.draft_assistant.service import clean_setting


def test_strips_a_trailing_comment() -> None:
    assert clean_setting("anthropic          # anthropic | openai") == "anthropic"


def test_strips_surrounding_whitespace() -> None:
    assert clean_setting("  openai \n") == "openai"


def test_leaves_a_clean_value_alone() -> None:
    assert clean_setting("claude-opus-5") == "claude-opus-5"


def test_handles_missing_value() -> None:
    assert clean_setting(None) == ""
    assert clean_setting("") == ""


def test_a_comment_only_value_is_empty_not_garbage() -> None:
    """So the "falta la key" error fires instead of sending junk to the API."""
    assert clean_setting("# pending") == ""
