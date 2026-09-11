"""A card has to carry what a side-by-side comparison needs.

Prioridad alone cannot separate two players who project the same: one has four
seasons in the same role, the other three matches since August. The board's
confidence indicator reads seasons, availability and the role-change flags;
the card must carry them, or the chat compares numbers the table already
knows are not equally trustworthy.
"""

from ..schemas import ViewContext
from ..tools import Toolset
from .factories import player, snapshot


def test_card_carries_the_comparison_fields() -> None:
    data = snapshot()
    row = data.players[0]
    row.exp_games_remaining = 12.5
    row.is_new = True
    row.team_changed = True
    card = data.card(row)
    assert card.avg_points == row.avg_points
    assert card.games_played == row.games_played
    assert card.seasons_played == row.seasons_played
    assert card.availability == row.availability
    assert card.exp_games_remaining == 12.5
    assert card.is_new is True
    assert card.team_changed is True
    assert card.position_changed is False


def test_the_fields_reach_the_tool_output() -> None:
    tools = Toolset(snapshot(), 11, ViewContext())
    out = tools.detail(1)
    assert '"seasons_played"' in out and '"availability"' in out


def test_a_player_without_history_is_flagged_not_faked() -> None:
    row = player(9)
    row.seasons_played = 0
    row.is_new = True
    card = snapshot().card(row)
    assert card.seasons_played == 0 and card.is_new is True


def test_the_card_names_the_season_its_figures_describe() -> None:
    """Without it, five matchdays of a new season read as a career: the chat
    would report a proven scorer as having no goals."""
    data = snapshot()
    row = data.players[0]
    row.ref_season_name = "2026-2027"
    card = data.card(row)
    assert card.ref_season_name == "2026-2027"


def test_the_card_carries_the_previous_season_when_there_is_one() -> None:
    from src.features.stats.schemas_draft import SeasonLine

    data = snapshot()
    row = data.players[0]
    row.previous_season = SeasonLine(
        season_name="2025-2026",
        games_played=30,
        goals=12,
        assists=5,
        total_points=210.0,
        avg_points=7.0,
        marca_avg=6.8,
        as_avg=2.4,
    )
    card = data.card(row)
    assert card.previous_season is not None
    assert card.previous_season.goals == 12
    assert card.previous_season.as_avg == 2.4


def test_a_player_with_no_past_carries_none_not_zeros() -> None:
    card = snapshot().card(snapshot().players[0])
    assert card.previous_season is None
