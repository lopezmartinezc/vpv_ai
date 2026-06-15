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
