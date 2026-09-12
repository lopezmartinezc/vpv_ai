"""The backup download must survive the ad-hoc snapshot tables left in the database.

pg_dump locks every table it dumps in one LOCK TABLE statement, so a single
snapshot owned by another role fails the entire backup:

    ERROR: permiso denegado a la tabla players_pos_snap_20260603_082710

That is what production returned. The fix excludes those tables, and the tests
below pin both halves: that the flag is actually passed to pg_dump, and that the
pattern covers the real table names that broke it without touching a real one.
"""

from __future__ import annotations

import asyncio
from fnmatch import fnmatch
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from src.app import create_app
from src.features.backup.router import SNAPSHOT_TABLES
from src.shared.dependencies import get_current_admin

# The exact LOCK TABLE list from the failing production backup.
SNAPSHOTS_IN_PRODUCTION = [
    "player_stats_snap_20260526_125520",
    "participant_matchday_scores_snap_20260526_125520",
    "lineup_players_snap_20260526_125520",
    "lineups_snap_20260526_125520",
    "players_pos_snap_20260603_082710",
]
REAL_TABLES = [
    "users",
    "seasons",
    "valid_formations",
    "scoring_rules",
    "season_payments",
    "season_participants",
    "teams",
    "competitions",
    "players",
    "drafts",
    "draft_picks",
    "matchdays",
    "matches",
    "player_stats",
    "lineups",
    "lineup_players",
    "participant_matchday_scores",
    "transactions",
    "invites",
    "player_ownership_log",
    "alembic_version",
    "achievement_definitions",
    "achievements",
    "push_subscriptions",
    "scraping_logs",
    "tournament_predictions",
    "draft_wishlists",
    "draft_wishlist_players",
    "competition_matchups",
    "draft_value_overrides",
    "draft_assistant_v2_chats",
]


class FakeProcess:
    def __init__(self, returncode: int, stdout: bytes, stderr: bytes) -> None:
        self.returncode = returncode
        self._out, self._err = stdout, stderr

    async def communicate(self) -> tuple[bytes, bytes]:
        return self._out, self._err


def client_with_admin(app: Any) -> AsyncClient:
    app.dependency_overrides[get_current_admin] = lambda: {"id": 1, "is_admin": True}
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.parametrize("table", SNAPSHOTS_IN_PRODUCTION)
def test_pattern_covers_every_snapshot_that_broke_production(table: str) -> None:
    assert fnmatch(table, SNAPSHOT_TABLES)


@pytest.mark.parametrize("table", REAL_TABLES)
def test_pattern_never_swallows_a_real_table(table: str) -> None:
    assert not fnmatch(table, SNAPSHOT_TABLES)


@pytest.mark.asyncio
async def test_pg_dump_is_told_to_exclude_them(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, tuple[str, ...]] = {}

    async def fake_exec(*argv: str, **_: Any) -> FakeProcess:
        captured["argv"] = argv
        return FakeProcess(0, b"-- PostgreSQL database dump\n", b"")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    async with client_with_admin(create_app()) as ac:
        response = await ac.post("/api/backup/admin/download")

    assert response.status_code == 200
    assert f"--exclude-table={SNAPSHOT_TABLES}" in captured["argv"]


@pytest.mark.asyncio
async def test_a_failing_dump_still_surfaces_why(monkeypatch: pytest.MonkeyPatch) -> None:
    """A backup that fails must say so — never hand back a truncated .sql as if it worked."""

    async def fake_exec(*_: str, **__: Any) -> FakeProcess:
        return FakeProcess(1, b"", b"pg_dump: error: permiso denegado a la tabla x")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    async with client_with_admin(create_app()) as ac:
        response = await ac.post("/api/backup/admin/download")

    assert response.status_code == 500
    assert "permiso denegado" in response.json()["message"]
