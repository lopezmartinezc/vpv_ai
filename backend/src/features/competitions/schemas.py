from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MatchupDraft(BaseModel):
    """In-memory description of a matchup before it is inserted in DB.

    A draft has either explicit participants OR feeder indices (which
    reference earlier slots in the same plugin batch). The service
    resolves feeder indices to actual ``competition_matchups.id``
    values after the first INSERT.
    """

    phase: str  # 'regular' | 'ko'
    round_number: int
    matchday_id: int | None = None
    participant_a_id: int | None = None
    participant_b_id: int | None = None
    group_label: str | None = None
    round_label: str | None = None
    # Local indices into the same draft batch; resolved by the service
    # into real DB ids after the first flush.
    feeder_a_index: int | None = None
    feeder_b_index: int | None = None


class MatchupEntry(BaseModel):
    id: int
    phase: str
    group_label: str | None = None
    round_label: str | None = None
    round_number: int
    matchday_id: int | None = None
    matchday_number: int | None = None
    participant_a_id: int | None = None
    participant_a_name: str | None = None
    participant_b_id: int | None = None
    participant_b_name: str | None = None
    feeder_a_id: int | None = None
    feeder_b_id: int | None = None
    score_a: int | None = None
    score_b: int | None = None
    winner_participant_id: int | None = None
    winner_name: str | None = None


class StandingEntry(BaseModel):
    rank: int
    participant_id: int
    display_name: str
    group_label: str = "overall"
    played: int
    wins: int
    draws: int
    losses: int
    rests: int
    points: int
    diff_avg: int
    pts_total_vpv: int


class GroupStandings(BaseModel):
    label: str
    entries: list[StandingEntry]


class CompetitionDetail(BaseModel):
    id: int
    season_id: int
    name: str
    type: str
    status: str  # 'pending' | 'regular' | 'ko' | 'completed'
    config: dict[str, Any] | None = None


class CompetitionMatchupsResponse(BaseModel):
    competition: CompetitionDetail
    matchups: list[MatchupEntry]


class CompetitionStandingsResponse(BaseModel):
    competition: CompetitionDetail
    groups: list[GroupStandings]


class CompetitionSummary(BaseModel):
    id: int
    season_id: int
    name: str
    type: str
    status: str


class CompetitionListResponse(BaseModel):
    season_id: int
    competitions: list[CompetitionSummary]


class FormatInfo(BaseModel):
    format_id: str
    display_name: str
    n_rounds_regular: int
    n_rounds_ko: int


class CreatePlayoffRequest(BaseModel):
    format_id: str = "balanced_ko4"


class StartRegularRequest(BaseModel):
    matchday_start: int = Field(ge=1)
    matchday_end: int = Field(ge=1)


class StartKoRequest(BaseModel):
    ko_matchday_numbers: list[int] = Field(min_length=1, max_length=10)
