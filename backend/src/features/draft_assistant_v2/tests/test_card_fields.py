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
