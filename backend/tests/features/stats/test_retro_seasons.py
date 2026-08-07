"""Retro/backtest must resolve league seasons dynamically.

Regression: the retrospective/backtest analytics used a hardcoded
VALID_SEASON_IDS = [5, 6, 7, 8], so for any season > 8 (e.g. 2026-27) they
kept training on 5-8 and ignored newer seasons. Now they query league
seasons from the DB.
"""

from __future__ import annotations

import pytest

from src.features.stats.service_draft_retro import DraftRetroService
from src.shared.models.season import Season


@pytest.mark.asyncio
async def test_league_season_ids_dynamic_and_before(db_session) -> None:
    # Mix of league + tournament seasons; tournaments must be excluded.
    league = []
    for name in ("2022-2023", "2023-2024", "2024-2025", "2025-2026", "2026-2027"):
        s = Season(name=name, matchday_start=1, kind="league")
        db_session.add(s)
        league.append(s)
    tourney = Season(name="Mundial 2026", matchday_start=1, kind="tournament")
    db_session.add(tourney)
    await db_session.flush()

    svc = DraftRetroService(db_session)

    all_ids = await svc._league_season_ids()
    league_ids = sorted(s.id for s in league)
    assert all_ids == league_ids  # only league, ascending, tournament excluded
    assert tourney.id not in all_ids

    # `before` = history strictly before a target season (backtest use).
    newest = league[-1].id  # 2026-2027
    before = await svc._league_season_ids(before=newest)
    assert newest not in before
    assert before == [i for i in league_ids if i < newest]
    # The newest season sees the 4 prior league seasons as history — NOT the
    # old hardcoded 5-8 cohort.
    assert len(before) == 4
