"""Schemas for draft value predictions."""

from __future__ import annotations

from pydantic import BaseModel


class DraftValuePlayer(BaseModel):
    player_id: int
    slug: str  # stable across seasons; used to join with historical rows
    display_name: str
    team_name: str
    position: str
    photo_path: str | None

    # Base stats
    games_played: int
    seasons_played: int
    avg_points: float
    total_points: float

    # === MODEL PREDICTIONS ===
    # V: Ensemble diverso (BEST overall — Spearman 0.718, Bust 10%)
    #    Average of: simple avg + minutes stability + career trend + 2nd half form
    #    USE FOR: main draft ranking
    ensemble_score: float

    # A: Simple average of last season (Spearman 0.711, MAE 1.46)
    #    USE FOR: baseline comparison — "what everyone sees"
    simple_avg: float

    # H: Second half weighted — finishing form predicts next season (Spearman 0.712)
    #    USE FOR: identifying players who ended strong (carry momentum)
    second_half_score: float | None

    # I: Productivity — G+A per 90 boosted (Spearman 0.712, Top26 27%)
    #    USE FOR: identifying productive attackers (DEL/MED)
    productivity_score: float

    # K: Minutes stability — rewards undisputed starters (Bust 10%)
    #    USE FOR: safe picks with low bust risk
    stability_score: float

    # C: Career trend — adjusts for year-over-year improvement/decline
    #    USE FOR: detecting rising or falling players
    trend_score: float | None

    # === SIGNALS (from individual models) ===
    career_trend_pct: float | None  # +20% = improving, -15% = declining
    marca_avg: float | None  # avg Marca stars (1-4)
    as_avg: float | None  # avg AS picas
    availability: float  # 0-1, games_45min / games
    consistency: float  # 1 - CV (0 = volatile, 1 = stable)
    second_half_avg: float | None  # avg pts J20-J38
    goals: int
    assists: int

    # === DRAFT SIGNAL ===
    # Composite signal based on ensemble + trend + availability
    signal: str  # "strong_buy" | "buy" | "hold" | "avoid"
    signal_reasons: list[str]  # ["Ensemble top 15%", "Trending up +18%", ...]

    # How much the current (partial) season weighed in the blend for this
    # player: n_current / (n_current + k). 1.0 = no history, pure current.
    weight_current: float | None = None

    # Draft board (VORP): projected value above the positional replacement
    # level, so DEF/MED/DEL/POR are comparable on a single cross-position
    # axis — the master sort of the draft board. position_rank is 1-based
    # within the player's position.
    vorp: float | None = None
    replacement_level: float | None = None
    position_rank: int | None = None

    # F2 — points reliability + durability.
    # event_share: fraction of points from concrete events (goals, assists,
    #   clean sheets, ...) vs subjective Marca/AS ratings — higher = more
    #   repeatable. exp_games_remaining: matchdays left * availability.
    #   proj_rest_points: projected points for the rest of the season.
    event_share: float | None = None
    exp_games_remaining: float | None = None
    proj_rest_points: float | None = None


class DraftValueResponse(BaseModel):
    season_id: int
    season_name: str
    matchdays_played: int
    draft_type: str  # "preseason" or "winter"
    peso_historico: float  # how much career data weighs (0-1)
    model_info: dict[str, str]  # model name → description
    players: list[DraftValuePlayer]
