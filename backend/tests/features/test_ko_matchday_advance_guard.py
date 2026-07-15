"""matchday_current must not skip a not-fully-materialised knockout round.

Regression for Mundial 2026 J7: only one of the two semifinals had a Match
row (the other was missing because the source calendar labelled the pending
fixture "1/2" instead of "Jornada 7"). scrape_match_players saw every
*existing* counting match as stats_ok and advanced the pointer to J8, so the
home view jumped to an empty next matchday. ``_expected_ko_pairings`` is the
guard that stops that: it reports how many fixtures the round should have.
"""

from __future__ import annotations

from types import SimpleNamespace

from src.features.scraping.service import ScrapingService

CONFIG = {
    "knockout": {
        "rounds": [
            {"matchday": 7, "pairings": [{"code": "M101"}, {"code": "M102"}]},
            {"matchday": 8, "pairings": [{"code": "M103"}, {"code": "M104"}]},
        ]
    }
}


def test_returns_pairing_count_for_ko_matchday() -> None:
    season = SimpleNamespace(kind="tournament", tournament_config=CONFIG)
    assert ScrapingService._expected_ko_pairings(season, 7) == 2
    assert ScrapingService._expected_ko_pairings(season, 8) == 2


def test_none_for_group_stage_or_unknown_matchday() -> None:
    season = SimpleNamespace(kind="tournament", tournament_config=CONFIG)
    # No knockout round declared for J3 → no guard (group stage).
    assert ScrapingService._expected_ko_pairings(season, 3) is None


def test_none_for_league_season() -> None:
    season = SimpleNamespace(kind="league", tournament_config=None)
    assert ScrapingService._expected_ko_pairings(season, 7) is None


def test_none_when_config_missing_or_malformed() -> None:
    assert (
        ScrapingService._expected_ko_pairings(
            SimpleNamespace(kind="tournament", tournament_config=None), 7
        )
        is None
    )
    assert (
        ScrapingService._expected_ko_pairings(
            SimpleNamespace(kind="tournament", tournament_config={"knockout": {}}), 7
        )
        is None
    )
