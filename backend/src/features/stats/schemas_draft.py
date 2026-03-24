"""Schemas for draft value predictions."""

from __future__ import annotations

from pydantic import BaseModel


class DraftValuePlayer(BaseModel):
    player_id: int
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


class DraftValueResponse(BaseModel):
    season_id: int
    season_name: str
    matchdays_played: int
    draft_type: str  # "preseason" or "winter"
    peso_historico: float  # how much career data weighs (0-1)
    model_info: dict[str, str]  # model name → description
    players: list[DraftValuePlayer]
