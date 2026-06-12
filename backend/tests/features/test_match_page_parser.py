"""Unit tests for parse_match_page_players + stats_source_for.

Anchors the Mundial scraping path (Mexico vs South Africa, World Cup
2026 group stage). Fixture lives in tests/fixtures/scraping/. When
futbolfantasy redesigns the page, these tests will fail loud and we
can update the fixture + parser together.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.features.scraping.config import stats_source_for
from src.features.scraping.parsers import (
    MatchPagePlayer,
    parse_match_page_players,
)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "scraping" / "match_mundial_mex_sud.html"


@pytest.fixture(scope="module")
def players() -> list[MatchPagePlayer]:
    html = FIXTURE.read_text(encoding="utf-8")
    return parse_match_page_players(
        html,
        matchday_number=1,
        home_team_name="México",
        away_team_name="Sudáfrica",
    )


class TestStatsSourceFor:
    """Config gate selects between the Liga and tournament strategies."""

    def test_default_is_player_page(self) -> None:
        assert stats_source_for(None) == "player_page"
        assert stats_source_for({}) == "player_page"
        assert stats_source_for({"other": "value"}) == "player_page"

    def test_explicit_match_page(self) -> None:
        assert stats_source_for({"stats_source": "match_page"}) == "match_page"

    def test_unknown_value_falls_back(self) -> None:
        # Defensive: silently default to player_page rather than crash.
        assert stats_source_for({"stats_source": "rss"}) == "player_page"


class TestParseMatchPage:
    """Shape checks against the real Mundial fixture."""

    def test_returns_52_players(self, players: list[MatchPagePlayer]) -> None:
        # 26 per team (11 starters + 15 sub slots).
        assert len(players) == 52

    def test_teams_evenly_split(self, players: list[MatchPagePlayer]) -> None:
        mex = [p for p in players if p.team_name == "México"]
        sud = [p for p in players if p.team_name == "Sudáfrica"]
        assert len(mex) == 26
        assert len(sud) == 26

    def test_11_starters_per_team(self, players: list[MatchPagePlayer]) -> None:
        mex_starters = [p for p in players if p.team_name == "México" and p.is_starter]
        sud_starters = [p for p in players if p.team_name == "Sudáfrica" and p.is_starter]
        assert len(mex_starters) == 11
        assert len(sud_starters) == 11

    def test_match_score_applied_to_all(self, players: list[MatchPagePlayer]) -> None:
        # México beat Sudáfrica 2-0 — every player carries this score.
        assert {p.stats.home_score for p in players} == {2}
        assert {p.stats.away_score for p in players} == {0}

    def test_result_perspective(self, players: list[MatchPagePlayer]) -> None:
        # Mexicans see a win (2), South Africans see a loss (0).
        mex_results = {p.stats.result for p in players if p.team_name == "México"}
        sud_results = {p.stats.result for p in players if p.team_name == "Sudáfrica"}
        assert mex_results == {2}
        assert sud_results == {0}


class TestStarterMinutes:
    """Substitution markers in the name infer minutes_played."""

    def test_unmarked_starter_played_full_90(self, players: list[MatchPagePlayer]) -> None:
        # Rangel is the unmarked starter GK — 90 minutes.
        rangel = next(p for p in players if "Rangel" in p.player_name_raw)
        assert rangel.is_starter is True
        assert rangel.stats.minutes_played == 90

    def test_starter_subbed_out_at_marked_minute(self, players: list[MatchPagePlayer]) -> None:
        # "Montes 91'" was subbed out (or red-carded) at minute 91.
        montes = next(p for p in players if "Montes 91" in p.player_name_raw)
        assert montes.is_starter is True
        assert montes.stats.minutes_played == 91

    def test_substitute_minute_in_name_means_came_on(self, players: list[MatchPagePlayer]) -> None:
        # Subs that appear with a minute came on at that minute and
        # played the remainder.
        subs_who_played = [p for p in players if not p.is_starter and p.stats.minutes_played > 0]
        # All non-starters with minutes < 90.
        assert all(0 < p.stats.minutes_played < 90 for p in subs_who_played)


class TestStatExtraction:
    """End-to-end checks on a few notable players."""

    def test_rangel_clean_sheet_and_picas(self, players: list[MatchPagePlayer]) -> None:
        rangel = next(p for p in players if "Rangel" in p.player_name_raw)
        # Mexico didn't concede — goals_against=0. The clean sheet itself
        # is derived downstream from goals_against by the ScoringEngine.
        assert rangel.stats.goals_against == 0
        # 1 picas (one <img class="pica">).
        assert rangel.stats.as_picas == "1"
        # "Paradas" (total saves) is NOT credited as penalties_saved —
        # VPV only scores penalty saves and the match page doesn't
        # surface those separately yet.
        assert rangel.stats.penalties_saved == 0

    def test_jimenez_scored_one(self, players: list[MatchPagePlayer]) -> None:
        jimenez = next(p for p in players if "Jiménez" in p.player_name_raw)
        assert jimenez.stats.goals == 1

    def test_quinones_scored_one(self, players: list[MatchPagePlayer]) -> None:
        quinones = next(p for p in players if "Quiñones" in p.player_name_raw)
        assert quinones.stats.goals == 1

    def test_montes_red_card(self, players: list[MatchPagePlayer]) -> None:
        # "Roja directa" img alt should flip the red flag.
        montes = next(p for p in players if "Montes 91" in p.player_name_raw)
        assert montes.stats.red_card is True

    def test_sithole_own_goal_error(self, players: list[MatchPagePlayer]) -> None:
        # "Error garrafal en gol en contra" img — count toward own_goals.
        sithole = next(p for p in players if "Sithole" in p.player_name_raw)
        assert sithole.stats.own_goals >= 1
        assert sithole.stats.red_card is True

    def test_yellow_card_detection(self, players: list[MatchPagePlayer]) -> None:
        # Brian Gutiérrez was booked (yellow).
        brian = next(p for p in players if "Brian Gutiérrez" in p.player_name_raw)
        assert brian.stats.yellow_card is True
        assert brian.stats.red_card is False


class TestSurnameCleaning:
    """Accent-folded, lowercased surname → key for DB matching."""

    def test_simple_surname(self, players: list[MatchPagePlayer]) -> None:
        rangel = next(p for p in players if "Rangel" in p.player_name_raw)
        assert rangel.surname_clean == "rangel"

    def test_accented_surname_is_folded(self, players: list[MatchPagePlayer]) -> None:
        jimenez = next(p for p in players if "Jiménez" in p.player_name_raw)
        # "jimenez", no accent.
        assert jimenez.surname_clean == "jimenez"

    def test_compound_name_keeps_last_word(self, players: list[MatchPagePlayer]) -> None:
        brian = next(p for p in players if "Brian Gutiérrez" in p.player_name_raw)
        assert brian.surname_clean == "gutierrez"

    def test_minute_markers_stripped(self, players: list[MatchPagePlayer]) -> None:
        montes = next(p for p in players if "Montes 91" in p.player_name_raw)
        assert montes.surname_clean == "montes"
