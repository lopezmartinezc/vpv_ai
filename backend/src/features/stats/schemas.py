"""Pydantic schemas for the admin statistics feature.

Three response envelopes served by three endpoints:
- PlayerStatsResponse   -> GET /stats/{season_id}/players
- ParticipantStatsResponse -> GET /stats/{season_id}/participants
- LeagueStatsResponse   -> GET /stats/{season_id}/league
"""

from __future__ import annotations

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Player stats — aggregated per player for a season
# ---------------------------------------------------------------------------


class PlayerStatRow(BaseModel):
    """Aggregated season stats for a single player (only matchdays that count)."""

    player_id: int
    display_name: str
    photo_path: str | None
    position: str  # Position used in player_stats (source of truth for scoring)
    team_name: str
    # Raw event counts
    goals: int
    penalty_goals: int
    own_goals: int
    assists: int
    penalties_saved: int
    yellow_cards: int
    red_cards: int  # Includes direct reds + double-yellows
    # Media ratings (may be None if no valid numeric data)
    avg_marca: float | None
    avg_as: float | None
    # Participation
    minutes_played: int
    matchdays_played: int
    started_count: int  # How many matchdays the player was a starter
    # Points
    avg_points: float  # total_points / matchdays_played
    total_points: int


class PlayerStatsResponse(BaseModel):
    season_id: int
    players: list[PlayerStatRow]


# ---------------------------------------------------------------------------
# Participant stats — point breakdowns + extremes + evolution per participant
# ---------------------------------------------------------------------------


class ParticipantBreakdown(BaseModel):
    """Cumulative point breakdown by scoring category for a participant's lineup."""

    participant_id: int
    display_name: str
    pts_play: int  # Points for playing (starter / substitute)
    pts_result: int  # Points from match result (win / draw / loss)
    pts_clean_sheet: int  # Clean-sheet bonus (DEF / POR)
    pts_goals: int  # Goals + penalty-goals combined
    pts_assists: int
    pts_yellow: int  # Penalty — negative
    pts_red: int  # Penalty — negative
    pts_marca_as: int  # Media (Marca + AS) combined bonus/penalty
    pts_total: int


class ParticipantExtremes(BaseModel):
    """Best / worst matchday and season average for a participant."""

    participant_id: int
    display_name: str
    best_points: int
    best_matchday: int
    worst_points: int
    worst_matchday: int
    avg_points: float


class EvolutionEntry(BaseModel):
    """Single data point in the cumulative point evolution chart."""

    matchday_number: int
    participant_id: int
    display_name: str
    points: int  # Points earned this matchday
    cumulative: int  # Running total up to this matchday


class ParticipantStatsResponse(BaseModel):
    season_id: int
    breakdowns: list[ParticipantBreakdown]
    extremes: list[ParticipantExtremes]
    evolution: list[EvolutionEntry]


# ---------------------------------------------------------------------------
# League stats — formations, most-lined-up players, matchday averages, records
# ---------------------------------------------------------------------------


class FormationUsage(BaseModel):
    """How many times a formation was used across all participants in a season."""

    formation: str
    usage_count: int


class MostLinedUpPlayer(BaseModel):
    """Player that appeared most frequently in any participant's lineup."""

    player_id: int
    display_name: str
    position: str
    team_name: str
    photo_path: str | None
    times_lined_up: int


class MatchdayAverage(BaseModel):
    """Aggregate point statistics for a single matchday across all participants."""

    matchday_number: int
    avg_points: float
    max_points: int
    min_points: int


class RecordEntry(BaseModel):
    """A notable league record (e.g. best individual score, worst matchday avg)."""

    label: str
    value: str
    detail: str


class LeagueStatsResponse(BaseModel):
    season_id: int
    formations: list[FormationUsage]
    most_lined_up: list[MostLinedUpPlayer]
    matchday_averages: list[MatchdayAverage]
    records: list[RecordEntry]
