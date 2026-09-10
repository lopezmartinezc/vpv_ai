"""The .env is shared by more than one settings class, and must stay loadable.

`Settings` in src/core declares no `extra`, and pydantic-settings defaults to
"forbid" — so any key in the .env file that is not one of its own fields
stops it from constructing. It is built at import time in src/core/config.py,
which means the whole backend refuses to boot: not one feature, all of them.

That is not hypothetical. `.env.example` documents ASSISTANT_V2_ENABLED,
the V2 chat's kill switch, and adding it to a production .env took the site
down with `Extra inputs are not permitted`. A kill switch that kills the
server is worse than no kill switch.

An OS environment variable never triggered this — only a line in the file —
which is why V2 ran fine for a day on its defaults.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.config import Settings
from src.features.draft_assistant_v2.config import AssistantSettings

BASE = "DATABASE_URL=postgresql+asyncpg://user:pass@localhost/db\nSECRET_KEY=x\n"


def _env(tmp_path: Path, extra: str) -> Path:
    path = tmp_path / ".env"
    path.write_text(BASE + extra, encoding="utf-8")
    return path


def test_another_components_variable_does_not_stop_the_core(tmp_path: Path) -> None:
    path = _env(tmp_path, "\nASSISTANT_V2_ENABLED=true\n")
    assert Settings(_env_file=str(path)).database_url.startswith("postgresql")


@pytest.mark.parametrize(
    "line",
    [
        "ASSISTANT_V2_ENABLED=false",
        "ASSISTANT_V2_MAX_ROUNDS=20",
        "ASSISTANT_V2_QUICK_EFFORT=low",
        "SOME_FUTURE_COMPONENT_SETTING=1",
    ],
)
def test_every_documented_v2_variable_is_survivable(tmp_path: Path, line: str) -> None:
    assert Settings(_env_file=str(_env(tmp_path, f"\n{line}\n"))) is not None


def test_the_v2_settings_still_read_their_own_values(tmp_path: Path) -> None:
    """Ignoring extras in the core must not mean the value goes unread: the
    class it belongs to still has to see it."""
    path = _env(tmp_path, "\nASSISTANT_V2_ENABLED=false\nASSISTANT_V2_MAX_ROUNDS=7\n")
    assistant = AssistantSettings(_env_file=str(path))
    assert assistant.enabled is False
    assert assistant.max_rounds == 7


def test_everything_in_the_shipped_example_loads() -> None:
    """The file we tell people to copy must not be a landmine."""
    example = Path(__file__).resolve().parents[2] / ".env.example"
    assert example.is_file(), example
    assert Settings(_env_file=str(example)) is not None
