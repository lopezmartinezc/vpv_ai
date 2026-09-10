"""Fixture difficulty, which is position-dependent.

Measured over 8 seasons, points lost by facing the hardest instead of the
easiest opponent:

    POR  2.58 by the opponent's ATTACK   1.62 by its defence
    DEF  1.55 by attack                  1.40 by defence
    MED  1.16 by attack                  1.57 by DEFENCE
    DEL  1.43 by attack                  2.04 by DEFENCE

So a keeper wants an opponent who cannot score and a forward wants one who
cannot defend. A single "hard fixture" number would average those two into
something wrong for everybody.
"""

from __future__ import annotations

import pytest

from src.features.stats.fixtures import (
    Fixture,
    TeamStrength,
    blend_strength,
    difficulty,
)


def _fx(attack: float, defence: float) -> Fixture:
    return Fixture(
        matchday=10,
        team_id=1,
        team_name="Getafe",
        opponent_id=2,
        opponent_name="Rival",
        home=True,
        opponent_attack=attack,
        opponent_defence=defence,
    )


class TestDifficulty:
    def test_keepers_are_graded_on_the_opponents_attack(self) -> None:
        prolific = _fx(attack=2.0, defence=1.3)
        toothless = _fx(attack=0.8, defence=1.3)
        assert difficulty("POR", prolific) == "dificil"
        assert difficulty("POR", toothless) == "facil"

    def test_forwards_are_graded_on_the_opponents_defence(self) -> None:
        leaky = _fx(attack=1.4, defence=1.7)
        solid = _fx(attack=1.4, defence=0.9)
        assert difficulty("DEL", leaky) == "facil"
        assert difficulty("DEL", solid) == "dificil"

    def test_the_same_fixture_is_easy_for_one_position_and_hard_for_another(self) -> None:
        # A side that scores freely and concedes freely: a nightmare for a
        # keeper, a gift for a forward. One number could not say both.
        wide_open = _fx(attack=2.0, defence=1.7)
        assert difficulty("POR", wide_open) == "dificil"
        assert difficulty("DEL", wide_open) == "facil"

    def test_midfielders_follow_the_defence_like_forwards(self) -> None:
        assert difficulty("MED", _fx(attack=1.4, defence=1.7)) == "facil"

    def test_defenders_follow_the_attack_like_keepers(self) -> None:
        assert difficulty("DEF", _fx(attack=2.0, defence=1.3)) == "dificil"

    def test_an_unknown_position_is_never_graded(self) -> None:
        assert difficulty("", _fx(attack=2.0, defence=1.7)) == "media"


class TestBlend:
    """Early in a season the current numbers are noise; late they are the truth."""

    HIST = TeamStrength(team_id=1, name="Getafe", attack=1.0, defence=1.0)
    NOW = TeamStrength(team_id=1, name="Getafe", attack=2.0, defence=2.0)

    def test_with_no_matchdays_played_it_is_all_history(self) -> None:
        out = blend_strength(self.HIST, self.NOW, played=0)
        assert out.attack == pytest.approx(1.0)

    def test_four_matchdays_still_lean_on_history(self) -> None:
        # 4 played against k=6: history keeps 60 % of the weight.
        out = blend_strength(self.HIST, self.NOW, played=4)
        assert out.attack == pytest.approx(1.4)

    def test_a_full_season_is_almost_all_current(self) -> None:
        out = blend_strength(self.HIST, self.NOW, played=30)
        assert out.attack > 1.8

    def test_a_team_with_no_history_uses_what_it_has(self) -> None:
        out = blend_strength(None, self.NOW, played=4)
        assert out.attack == pytest.approx(2.0)

    def test_a_team_with_neither_falls_back_to_the_league_average(self) -> None:
        out = blend_strength(None, None, played=0, team_id=9, name="Nuevo")
        assert out.attack > 0
        assert out.defence > 0
