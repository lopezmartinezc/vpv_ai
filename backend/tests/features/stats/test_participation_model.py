"""Two ways to estimate how much of the season a player will feature in.

``historico`` is what the board has always done: games over that season's
matchdays. ``mixto`` blends in what this season is already showing — above all
the minutes he is getting AT HIS POSITION AND CLUB, which is the difference
between "he plays" and "they are giving the minutes to him and not the other
one".

Measured on held-out seasons, predicting participation over the rest of the
season: 0.655 for historico, 0.730 for mixto. Participation multiplies straight
into proj_rest_points and therefore into Prioridad, so the whole board reorders
— which is why it ships behind a switch that defaults to the old behaviour.
"""

from __future__ import annotations

import pytest

from src.features.stats.participation import (
    ParticipationModel,
    blended_participation,
    minute_shares,
    season_participation,
)


class _Season:
    """Enough of _PlayerSeason for the participation maths."""

    def __init__(
        self,
        slug: str,
        games: int,
        minutes: int,
        team_name: str = "Getafe",
        position: str = "MED",
        season_id: int = 12,
    ) -> None:
        self.slug = slug
        self.games = games
        self.minutes = minutes
        self.team_name = team_name
        self.position = position
        self.season_id = season_id


TOTALS = {11: 38, 12: 5}


class TestMinuteShares:
    """Share of a full load in his own slot: minutes over (matchdays his club
    has played at that position) x 90. The club+position pool sets how many
    matchdays that is, so a club with a game in hand is not read as a player
    missing a game."""

    def test_an_ever_present_gets_the_full_share(self) -> None:
        assert minute_shares([_Season("solo", 5, 450)])["solo"] == pytest.approx(1.0)

    def test_the_man_losing_the_slot_gets_less_of_it(self) -> None:
        rows = [_Season("a", 5, 400), _Season("b", 5, 100)]
        shares = minute_shares(rows)
        assert shares["a"] == pytest.approx(400 / 450)
        assert shares["b"] == pytest.approx(100 / 450)

    def test_another_position_at_the_same_club_is_a_separate_pool(self) -> None:
        # The defender must not be measured against the midfielders' matchdays.
        rows = [
            _Season("mid", 5, 450, position="MED"),
            _Season("def", 5, 450, position="DEF"),
        ]
        shares = minute_shares(rows)
        assert shares["mid"] == pytest.approx(1.0)
        assert shares["def"] == pytest.approx(1.0)

    def test_a_club_with_a_game_in_hand_is_judged_on_its_own_matchdays(self) -> None:
        rows = [
            _Season("getafe-man", 5, 450, team_name="Getafe"),
            _Season("alaves-man", 3, 270, team_name="Alavés"),
        ]
        shares = minute_shares(rows)
        assert shares["getafe-man"] == pytest.approx(1.0)
        assert shares["alaves-man"] == pytest.approx(1.0)

    def test_it_never_exceeds_a_full_load(self) -> None:
        # Extra time, or a slot whose leader missed a game: still capped at 1.
        rows = [_Season("a", 3, 300), _Season("b", 3, 200)]
        assert minute_shares(rows)["a"] == pytest.approx(1.0)

    def test_no_minutes_anywhere_is_not_a_division_by_zero(self) -> None:
        assert minute_shares([_Season("x", 0, 0)])["x"] == pytest.approx(0.0)


class TestSeasonParticipation:
    """The historico rate, unchanged: games over that season's matchdays."""

    def test_half_a_season_is_half(self) -> None:
        assert season_participation(_Season("x", 19, 1700, season_id=11), TOTALS) == pytest.approx(
            0.5
        )

    def test_it_caps_at_one(self) -> None:
        assert season_participation(_Season("x", 40, 3600, season_id=11), TOTALS) == pytest.approx(
            1.0
        )

    def test_nothing_is_zero(self) -> None:
        assert season_participation(None, TOTALS) == pytest.approx(0.0)


class TestBlend:
    HIST = _Season("x", 19, 1700, season_id=11)  # half of 38
    NAILED = _Season("x", 5, 450, season_id=12)  # every minute so far

    def _mixto(self, **kw: object) -> float:
        args: dict = {
            "ref": self.NAILED,
            "hist": self.HIST,
            "current": self.NAILED,
            "minute_share": 1.0,
            "md_played": 5,
            "season_total_md": TOTALS,
        }
        args.update(kw)
        return blended_participation(ParticipationModel.MIXTO, **args)

    def test_historico_is_the_plain_rate_of_the_reference_season(self) -> None:
        assert blended_participation(
            ParticipationModel.HISTORICO,
            ref=self.HIST,
            hist=self.HIST,
            current=None,
            minute_share=None,
            md_played=5,
            season_total_md=TOTALS,
        ) == pytest.approx(0.5)

    def test_historico_reads_whichever_season_the_caller_points_it_at(self) -> None:
        """The caller hands it ``ref``; a current sample too thin to trust is
        not passed as ref, and historico then never sees this season at all."""
        assert blended_participation(
            ParticipationModel.HISTORICO,
            ref=self.NAILED,
            hist=self.HIST,
            current=self.NAILED,
            minute_share=1.0,
            md_played=5,
            season_total_md=TOTALS,
        ) == pytest.approx(1.0)

    def test_mixto_lifts_a_player_who_is_now_undisputed(self) -> None:
        assert 0.5 < self._mixto() < 1.0

    def test_mixto_drops_a_player_who_has_lost_the_shirt(self) -> None:
        benched = _Season("x", 1, 30, season_id=12)
        assert self._mixto(current=benched, minute_share=0.1) < 0.5

    def test_playing_every_game_off_the_bench_is_not_a_starter(self) -> None:
        """Appearances alone say yes; minutes say no. The blend must land
        between the two, which is the whole point of weighting the share."""
        cameos = _Season("x", 5, 100, season_id=12)
        assert self._mixto(current=cameos, minute_share=100 / 450) < self._mixto()

    def test_before_a_ball_is_kicked_mixto_equals_historico(self) -> None:
        """At zero matchdays the current signals do not exist, so their weight
        has to be zero — not the weight measured at five."""
        assert self._mixto(current=None, minute_share=None, md_played=0) == pytest.approx(0.5)

    def test_this_season_earns_weight_as_it_accumulates(self) -> None:
        def at(md: int) -> float:
            return self._mixto(
                current=_Season("x", md, md * 90, season_id=12),
                md_played=md,
                season_total_md={11: 38, 12: md},
            )

        assert at(2) < at(10) < at(25)

    def test_a_player_with_no_history_leans_on_this_season(self) -> None:
        assert self._mixto(hist=None) > 0.8

    def test_nothing_at_all_is_zero_not_a_guess(self) -> None:
        assert blended_participation(
            ParticipationModel.MIXTO,
            ref=None,
            hist=None,
            current=None,
            minute_share=None,
            md_played=5,
            season_total_md=TOTALS,
        ) == pytest.approx(0.0)

    def test_it_never_exceeds_a_full_season(self) -> None:
        assert self._mixto(hist=_Season("x", 40, 3600, season_id=11)) <= 1.0
