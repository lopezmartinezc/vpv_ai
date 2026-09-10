"""How much of the remaining season a player will actually feature in.

Participation multiplies straight into ``proj_rest_points``, so it is worth
roughly half of everything the draft board ranks on: a 30-point-per-game player
who features in 60% of matchdays is a worse pick than a 22-point player who
plays every week.

Two models, switchable per request:

``historico``
    Games over that season's matchdays, on the reference season (this one if it
    has started, otherwise the last one). This is what the board has always
    done and stays the default.

``mixto``
    Blends the historical rate with what THIS season is already showing. The
    signal that carries it is not "has he played" but "is the club giving the
    minutes in his slot to him or to the other one" — a squad player racking up
    twenty-minute cameos looks nailed-on if you count appearances and looks
    exactly like what he is if you count minutes.

Backtested on held-out seasons, predicting participation over the rest of the
season: 0.655 for historico, 0.730 for mixto.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from enum import StrEnum
from typing import Protocol

MINUTES_PER_MATCH = 90

# Weight on this season's signals, as md_played/(md_played+K). K is calibrated
# so that five matchdays in — where the backtest was run, and where the Liga
# draft happens — this season carries 0.65 and history 0.35. It keeps rising
# afterwards, which is what we want: by the winter draft the current season is
# simply better evidence than the previous one.
CURRENT_WEIGHT_K = 2.69

# Split of that 0.65 between the two current-season signals (0.45 / 0.20 of the
# whole, renormalised to sum to 1 here).
SHARE_WEIGHT = 0.45 / 0.65
APPEARANCE_WEIGHT = 0.20 / 0.65


class ParticipationModel(StrEnum):
    HISTORICO = "historico"
    MIXTO = "mixto"


class SeasonRow(Protocol):
    """The fields of a player-season the participation maths needs."""

    slug: str
    position: str
    team_name: str
    season_id: int
    games: int
    minutes: int


def minute_shares(rows: Sequence[SeasonRow]) -> dict[str, float]:
    """Share of a full load in his own slot, per slug.

    The pool is club + position: minutes over ``matchdays the club has played
    at that position x 90``, where those matchdays are taken as the most any
    single player in the pool has appeared in. Anchoring to the pool rather
    than to a league-wide matchday count means a club with a game in hand — or
    a postponement — is judged on the games it has actually played, instead of
    reading every one of its players as having missed one.
    """

    pools: dict[tuple[str, str], list[SeasonRow]] = defaultdict(list)
    for row in rows:
        pools[(row.team_name.strip().lower(), row.position)].append(row)

    shares: dict[str, float] = {}
    for pool in pools.values():
        pool_md = max(row.games for row in pool)
        full_load = pool_md * MINUTES_PER_MATCH
        for row in pool:
            shares[row.slug] = min(1.0, row.minutes / full_load) if full_load else 0.0
    return shares


def season_participation(
    row: SeasonRow | None,
    season_total_md: dict[int, int],
) -> float:
    """Games played over that season's matchdays, capped at a full season."""

    if row is None:
        return 0.0
    total = max(1, season_total_md.get(row.season_id, row.games))
    return min(1.0, row.games / total)


def blended_participation(
    model: ParticipationModel,
    *,
    ref: SeasonRow | None,
    hist: SeasonRow | None,
    current: SeasonRow | None,
    minute_share: float | None,
    md_played: int,
    season_total_md: dict[int, int],
) -> float:
    """Expected share of the remaining matchdays the player will feature in.

    ``ref`` is the season historico reads — this one when its sample is thick
    enough to trust, otherwise the last one — and the caller owns that choice
    because the rest of the board displays the same row. ``hist`` is the most
    recent prior season and ``current`` this one so far; pass the latter even
    when its sample is too thin for the points projection, since one
    appearance out of five is exactly the signal mixto is after.
    ``minute_share`` is his value from :func:`minute_shares`.
    """

    if model is ParticipationModel.HISTORICO:
        return season_participation(ref, season_total_md)

    historical = season_participation(hist, season_total_md)
    weight = md_played / (md_played + CURRENT_WEIGHT_K) if md_played > 0 else 0.0

    if current is None or md_played <= 0:
        # Nothing to blend in — including preseason, where the weight on a
        # season that has not started has to be zero rather than the 0.65 the
        # backtest measured at matchday five.
        return historical if hist is not None else 0.0

    appearances = min(1.0, current.games / md_played)
    share = minute_share if minute_share is not None else appearances
    signal = SHARE_WEIGHT * share + APPEARANCE_WEIGHT * appearances

    if hist is None:
        # No prior season: the current one is all the evidence there is, and
        # shrinking it toward a zero prior would bury every newcomer.
        return min(1.0, signal)

    return min(1.0, (1.0 - weight) * historical + weight * signal)
