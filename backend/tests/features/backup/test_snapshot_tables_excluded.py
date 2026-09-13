"""The backup download: what it leaves out, and what it must never hand back.

Two separate failures live here.

The first was a real production outage. pg_dump locks every table it dumps in
one LOCK TABLE statement, so a single snapshot owned by another role failed the
entire backup:

    ERROR: permiso denegado a la tabla players_pos_snap_20260603_082710

The second is the one that would have been worse: a dump that breaks partway
through must not reach the admin looking like a whole one. The response is
already in flight by then and cannot be taken back, so the gzip trailer is never
written and the file reads as corrupt — which is the truth about it.
"""

from __future__ import annotations

import asyncio
import gzip
import zlib
from fnmatch import fnmatch
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from src.app import create_app
from src.features.backup import router as backup
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


class FakeStream:
    """Hands out `payload` in pieces, so a test can prove we read incrementally."""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self._at = 0
        self.reads: list[int] = []

    async def read(self, n: int = -1) -> bytes:
        self.reads.append(n)
        if n < 0:
            chunk, self._at = self._payload[self._at :], len(self._payload)
            return chunk
        chunk = self._payload[self._at : self._at + n]
        self._at += len(chunk)
        return chunk


class FakeProcess:
    def __init__(self, stdout: bytes, stderr: bytes = b"", returncode: int = 0) -> None:
        self.stdout = FakeStream(stdout)
        self.stderr = FakeStream(stderr)
        self.returncode = returncode

    async def wait(self) -> int:
        return self.returncode


def admin_client(app: Any) -> AsyncClient:
    app.dependency_overrides[get_current_admin] = lambda: {"id": 1, "is_admin": True}
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def spawn(process: FakeProcess, captured: dict[str, Any] | None = None) -> Any:
    async def fake_exec(*argv: str, **_: Any) -> FakeProcess:
        if captured is not None:
            captured["argv"] = argv
        return process

    return fake_exec


# --- what the dump leaves out ------------------------------------------------


@pytest.mark.parametrize("table", SNAPSHOTS_IN_PRODUCTION)
def test_pattern_covers_every_snapshot_that_broke_production(table: str) -> None:
    assert fnmatch(table, backup.SNAPSHOT_TABLES)


@pytest.mark.parametrize("table", REAL_TABLES)
def test_pattern_never_swallows_a_real_table(table: str) -> None:
    assert not fnmatch(table, backup.SNAPSHOT_TABLES)


@pytest.mark.asyncio
async def test_pg_dump_is_told_to_exclude_them(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        asyncio, "create_subprocess_exec", spawn(FakeProcess(b"-- dump\n"), captured)
    )

    async with admin_client(create_app()) as ac:
        response = await ac.post("/api/backup/admin/download")

    assert response.status_code == 200
    assert f"--exclude-table={backup.SNAPSHOT_TABLES}" in captured["argv"]


# --- what the admin actually receives ----------------------------------------


@pytest.mark.asyncio
async def test_the_download_is_gzip_that_decompresses_to_the_dump(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dump = b"-- PostgreSQL database dump\n" + b"INSERT INTO player_stats ...\n" * 5000
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn(FakeProcess(dump)))

    async with admin_client(create_app()) as ac:
        response = await ac.post("/api/backup/admin/download")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/gzip"
    assert response.headers["content-disposition"].endswith('.sql.gz"')
    assert gzip.decompress(response.content) == dump
    assert len(response.content) < len(dump), "a gzipped SQL dump should be far smaller"


@pytest.mark.asyncio
async def test_the_dump_is_never_held_in_memory_whole() -> None:
    """Read in bounded chunks: the old version buffered the entire dump in RAM."""
    chunks_of_dump = 7
    dump = b"x" * chunks_of_dump * backup.CHUNK_BYTES
    process = FakeProcess(dump)

    out = b"".join(
        [
            chunk
            async for chunk in backup._gzipped(
                process,  # type: ignore[arg-type]
                asyncio.create_task(process.stderr.read()),
                await process.stdout.read(backup.CHUNK_BYTES),
                "ligavpv.sql.gz",
            )
        ]
    )

    assert gzip.decompress(out) == dump
    assert all(n == backup.CHUNK_BYTES for n in process.stdout.reads)
    assert len(process.stdout.reads) > chunks_of_dump, "one read per chunk, not one big read"


# --- what must never look like a good backup ---------------------------------


@pytest.mark.asyncio
async def test_a_dump_that_fails_before_any_output_gets_a_clean_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    denied = b"pg_dump: error: permiso denegado a la tabla players_pos_snap_20260603_082710"
    monkeypatch.setattr(
        asyncio, "create_subprocess_exec", spawn(FakeProcess(b"", denied, returncode=1))
    )

    async with admin_client(create_app()) as ac:
        response = await ac.post("/api/backup/admin/download")

    assert response.status_code == 500
    assert "permiso denegado" in response.json()["message"]


@pytest.mark.asyncio
async def test_a_dump_that_dies_midway_yields_a_file_gunzip_rejects() -> None:
    """The half-dump must not be a valid .gz — a truncated backup that opens fine
    is worse than no backup, because it is trusted."""
    process = FakeProcess(b"-- PostgreSQL database dump\n" * 400, b"server closed", returncode=1)

    chunks: list[bytes] = []
    with pytest.raises(RuntimeError):
        async for chunk in backup._gzipped(
            process,  # type: ignore[arg-type]
            asyncio.create_task(process.stderr.read()),
            await process.stdout.read(backup.CHUNK_BYTES),
            "ligavpv.sql.gz",
        ):
            chunks.append(chunk)

    with pytest.raises((EOFError, zlib.error, gzip.BadGzipFile)):
        gzip.decompress(b"".join(chunks))
