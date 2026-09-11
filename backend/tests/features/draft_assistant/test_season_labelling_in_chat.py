"""The chat must not call this season's five matchdays a player's history.

The board's raw figures describe the REFERENCE season, which becomes the
current one as soon as it has a couple of appearances. V1's player detail
printed them under "Historico:", so five matchdays into a season a proven
scorer reads as "Historico: 5 partidos, 0 goles" — the same trap the expanded
row had, made worse by a label that asserts it is history.

And a tag the prompt does not list is a tag the model treats as noise: V1
enumerates them, so an omission reads as "this does not exist".
"""

from __future__ import annotations

from src.features.draft_assistant.board_tools import _player_detail
from src.features.draft_assistant.service import SYSTEM_PROMPT
from src.features.stats.schemas_draft import DraftValuePlayer, SeasonLine


def _player(**over) -> DraftValuePlayer:
    base = {
        "player_id": 1,
        "slug": "cucho",
        "display_name": "Cucho",
        "team_name": "Betis",
        "position": "DEL",
        "photo_path": None,
        "games_played": 5,
        "seasons_played": 4,
        "avg_points": 4.0,
        "total_points": 20.0,
        "ensemble_score": 6.0,
        "simple_avg": 6.0,
        "second_half_score": None,
        "productivity_score": 6.0,
        "stability_score": 6.0,
        "trend_score": None,
        "career_trend_pct": None,
        "marca_avg": None,
        "as_avg": None,
        "availability": 1.0,
        "consistency": 1.0,
        "second_half_avg": None,
        "goals": 0,
        "assists": 0,
        "signal": "hold",
        "signal_reasons": [],
        "ref_season_name": "2026-2027",
        "previous_season": SeasonLine(
            season_name="2025-2026",
            games_played=30,
            goals=12,
            assists=5,
            total_points=210.0,
            avg_points=7.0,
            marca_avg=6.8,
            as_avg=2.4,
        ),
    }
    base.update(over)
    return DraftValuePlayer(**base)


def test_the_figures_are_named_by_their_season_not_called_history() -> None:
    text = _player_detail(_player())
    assert "2026-2027" in text
    assert "Historico:" not in text


def test_the_previous_season_is_offered_alongside() -> None:
    """The number a drafter asking about a scorer is actually after."""
    text = _player_detail(_player())
    assert "2025-2026" in text
    assert "12 goles" in text
    assert "30 partidos" in text or "30 PJ" in text


def test_both_press_marks_travel_with_it() -> None:
    text = _player_detail(_player())
    assert "6.8" in text and "2.4" in text


def test_a_player_with_no_past_says_nothing_rather_than_zeros() -> None:
    text = _player_detail(_player(previous_season=None, seasons_played=0))
    assert "2025-2026" not in text
    # And it still names the season the figures do describe.
    assert "2026-2027" in text


def test_the_prompt_lists_every_tag_the_board_accepts() -> None:
    """An enumerated list with a gap reads as 'that tag does not exist'."""
    from src.features.stats.service_draft import ALLOWED_TAGS

    for tag in ALLOWED_TAGS:
        assert tag in SYSTEM_PROMPT, tag
