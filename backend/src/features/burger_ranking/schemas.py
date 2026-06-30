"""Pydantic schemas for the Burger Ranking endpoint.

The Burger Ranking counts goals scored by a participant's OWNED players
that were NOT in the participant's lineup for that matchday — one 🍔 per
goal "lost on the bench". Penalties count, own goals don't.
"""

from __future__ import annotations

from pydantic import BaseModel


class BurgerGoal(BaseModel):
    """A single matchday-and-player record contributing to the burger total."""

    matchday_number: int
    player_id: int
    player_name: str
    team_name: str
    goals: int  # number of goals that player scored that matchday (1, 2, …)


class BurgerEntry(BaseModel):
    """One participant's burger ranking row + breakdown."""

    participant_id: int
    display_name: str
    total: int  # SUM of `goals` across goals[]
    goals: list[BurgerGoal]


class BurgerRankingResponse(BaseModel):
    """Full ranking for a season, sorted by total DESC."""

    season_id: int
    entries: list[BurgerEntry]


# Bench ranking ------------------------------------------------------


class BenchedPlayer(BaseModel):
    """A single matchday-and-player record where the manager lined the
    player up but they played 0 minutes (not called, late injury, …)."""

    matchday_number: int
    player_id: int
    player_name: str
    team_name: str
    position: str


class BenchEntry(BaseModel):
    """One participant's bench-ranking row + breakdown."""

    participant_id: int
    display_name: str
    total: int  # count of (matchday, player) pairs in players[]
    players: list[BenchedPlayer]


class BenchRankingResponse(BaseModel):
    season_id: int
    entries: list[BenchEntry]


# Combined endpoint --------------------------------------------------


# Survivors ranking (tournaments only) ------------------------------


class SurvivorPlayer(BaseModel):
    """One owned player and whether their national team is still in."""

    player_id: int
    player_name: str
    team_name: str
    position: str
    alive: bool


class SurvivorEntry(BaseModel):
    """One participant's survivors row + per-player breakdown."""

    participant_id: int
    display_name: str
    alive_count: int
    eliminated_count: int
    total: int
    players: list[SurvivorPlayer]


class SurvivorsResponse(BaseModel):
    season_id: int
    # False while the group stage is undecided (everyone still alive).
    group_stage_done: bool
    entries: list[SurvivorEntry]


# Combined endpoint --------------------------------------------------


class RankingsResponse(BaseModel):
    """Two (or three) rankings in one round-trip for the /ranking page.

    ``survivors`` is populated only for tournament seasons; it stays ``None``
    for leagues, where elimination has no meaning.
    """

    season_id: int
    burger: BurgerRankingResponse
    bench: BenchRankingResponse
    survivors: SurvivorsResponse | None = None
