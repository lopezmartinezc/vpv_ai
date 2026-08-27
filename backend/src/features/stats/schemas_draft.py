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

    # Preseason draft board.
    # auto_projection: value the model projects (None for a brand-new player
    #   with no history and no current stats). manual_value/note: admin
    #   override. effective_value = manual_value if set else auto_projection —
    #   what VORP is computed on. Flags surface who needs a manual look.
    auto_projection: float | None = None
    manual_value: float | None = None
    note: str | None = None
    effective_value: float | None = None
    is_new: bool = False  # no prior-season history
    team_changed: bool = False  # roster team differs from last historical season
    position_changed: bool = False  # roster position differs from last historical season
    # Risk flags (scorecard). is_peak_year: last season well above career avg
    #   (regression risk). is_penalty_taker: DEL who took penalties last season
    #   (ceiling bonus, ~44% persists). is_bench_risk: rotation/availability risk.
    is_peak_year: bool = False
    is_penalty_taker: bool = False
    is_bench_risk: bool = False

    # Positional tier from the scorecard (elite | solid | normal | weak;
    # "team_dependent" for POR). None for brand-new players with no history.
    position_tier: str | None = None
    # Draft priority: projected rest-of-season points, risk-adjusted (peak-year,
    # bench risk, low reliability). The MASTER sort — ordering by projected total
    # beats per-game VORP at predicting real points. None without a projection.
    priority: float | None = None
    # 1-based rank across ALL positions by priority (the draft order / ADP).
    # None for players without a projection. Combined with
    # ``DraftValueResponse.participant_count`` gives the estimated round.
    overall_rank: int | None = None


class DraftValueResponse(BaseModel):
    season_id: int
    season_name: str
    matchdays_played: int
    draft_type: str  # "preseason" or "winter"
    peso_historico: float  # how much career data weighs (0-1)
    model_info: dict[str, str]  # model name → description
    # Number of season participants — the round size for the ADP estimate
    # (round = ceil(overall_rank / participant_count)). 0 if unknown.
    participant_count: int = 0
    players: list[DraftValuePlayer]


class DraftValueOverrideRequest(BaseModel):
    """Admin manual override for a player on the draft board. A null
    ``manual_value`` clears the override back to the automatic projection."""

    manual_value: float | None = None
    note: str | None = None
