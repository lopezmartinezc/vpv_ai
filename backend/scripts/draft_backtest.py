"""Draft model backtesting — compare prediction models across validation windows.

Uses seasons 5-8 (2022-2023 onwards) where scoring rules are consistent.
Tests two scenarios: preseason draft (history only) and winter draft (history + partial season).

Usage:
    cd backend && source .venv/bin/activate
    python -m scripts.draft_backtest
    python -m scripts.draft_backtest --output results.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import random
import statistics
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from scipy import stats as scipy_stats
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")
log = logging.getLogger(__name__)

VALID_SEASON_IDS = [5, 6, 7, 8]
MIN_GAMES = 10
DRAFT_PARTICIPANTS = 8
DRAFT_PICKS = 26
RANDOM_TRIALS = 100


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class PlayerSeason:
    slug: str
    display_name: str
    position: str
    season_id: int
    season_name: str
    games: int
    games_45min: int
    avg_pts: float
    total_pts: float
    std_pts: float
    marca_avg: float | None
    as_avg: float | None
    # Extended fields
    goals: int = 0
    assists: int = 0
    minutes: int = 0
    first_half_avg: float = 0  # J start..J19
    second_half_avg: float = 0  # J20..J38
    yellows: int = 0
    team_name: str = ""


@dataclass
class PlayerPartial:
    """Stats from a partial season (pre-winter-draft matchdays)."""

    slug: str
    avg_pts: float
    games: int
    marca_avg: float | None
    as_avg: float | None


@dataclass
class SeasonConfig:
    id: int
    name: str
    matchday_start: int
    matchday_winter: int


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


async def load_season_configs(session: AsyncSession) -> dict[int, SeasonConfig]:
    result = await session.execute(
        text("""
            SELECT id, name, matchday_start, matchday_winter
            FROM seasons WHERE id = ANY(:ids) ORDER BY id
        """),
        {"ids": VALID_SEASON_IDS},
    )
    return {
        r.id: SeasonConfig(r.id, r.name, r.matchday_start, r.matchday_winter or 20)
        for r in result.all()
    }


async def load_full_seasons(session: AsyncSession) -> list[PlayerSeason]:
    """Load full-season aggregates for valid seasons."""
    result = await session.execute(
        text("""
            SELECT p.slug, p.display_name, ps.position,
                   md.season_id, s.name as season_name, t.name as team_name,
                   COUNT(*) as games,
                   COUNT(CASE WHEN ps.minutes_played >= 45 THEN 1 END) as games_45min,
                   AVG(ps.pts_total) as avg_pts,
                   SUM(ps.pts_total) as total_pts,
                   STDDEV(ps.pts_total) as std_pts,
                   AVG(CASE WHEN ps.marca_rating ~ '^[1-4]$'
                       THEN CAST(ps.marca_rating AS INTEGER) END) as marca_avg,
                   AVG(CASE WHEN ps.as_picas ~ '^[0-9]+$'
                       THEN CAST(ps.as_picas AS INTEGER) END) as as_avg,
                   COALESCE(SUM(ps.goals + ps.penalty_goals), 0) as goals,
                   COALESCE(SUM(ps.assists), 0) as assists,
                   COALESCE(SUM(ps.minutes_played), 0) as minutes,
                   AVG(CASE WHEN md.number <= 19 THEN ps.pts_total END) as first_half_avg,
                   AVG(CASE WHEN md.number > 19 THEN ps.pts_total END) as second_half_avg,
                   COALESCE(SUM(CASE WHEN ps.yellow_card THEN 1 ELSE 0 END), 0) as yellows
            FROM player_stats ps
            JOIN players p ON ps.player_id = p.id
            JOIN matchdays md ON ps.matchday_id = md.id AND md.counts = TRUE
            JOIN teams t ON p.team_id = t.id
            JOIN seasons s ON md.season_id = s.id
            WHERE md.season_id = ANY(:ids)
            GROUP BY p.slug, p.display_name, ps.position, md.season_id, s.name, t.name
            HAVING COUNT(*) >= :min
            ORDER BY p.slug, md.season_id
        """),
        {"ids": VALID_SEASON_IDS, "min": MIN_GAMES},
    )
    return [
        PlayerSeason(
            slug=r.slug, display_name=r.display_name, position=r.position,
            season_id=r.season_id, season_name=r.season_name,
            games=r.games, games_45min=r.games_45min,
            avg_pts=float(r.avg_pts or 0), total_pts=float(r.total_pts or 0),
            std_pts=float(r.std_pts or 0),
            marca_avg=float(r.marca_avg) if r.marca_avg is not None else None,
            as_avg=float(r.as_avg) if r.as_avg is not None else None,
            goals=int(r.goals or 0), assists=int(r.assists or 0),
            minutes=int(r.minutes or 0),
            first_half_avg=float(r.first_half_avg or 0),
            second_half_avg=float(r.second_half_avg or 0),
            yellows=int(r.yellows or 0),
            team_name=r.team_name or "",
        )
        for r in result.all()
    ]


async def load_partial_season(
    session: AsyncSession, season_id: int, max_matchday: int
) -> list[PlayerPartial]:
    """Load stats for matchdays start..max_matchday of a season (pre-winter-draft)."""
    result = await session.execute(
        text("""
            SELECT p.slug,
                   AVG(ps.pts_total) as avg_pts,
                   COUNT(*) as games,
                   AVG(CASE WHEN ps.marca_rating ~ '^[1-4]$'
                       THEN CAST(ps.marca_rating AS INTEGER) END) as marca_avg,
                   AVG(CASE WHEN ps.as_picas ~ '^[0-9]+$'
                       THEN CAST(ps.as_picas AS INTEGER) END) as as_avg
            FROM player_stats ps
            JOIN players p ON ps.player_id = p.id
            JOIN matchdays md ON ps.matchday_id = md.id AND md.counts = TRUE
            WHERE md.season_id = :sid AND md.number <= :max_md
            GROUP BY p.slug
            HAVING COUNT(*) >= 3
        """),
        {"sid": season_id, "max_md": max_matchday},
    )
    return [
        PlayerPartial(
            slug=r.slug, avg_pts=float(r.avg_pts or 0), games=r.games,
            marca_avg=float(r.marca_avg) if r.marca_avg is not None else None,
            as_avg=float(r.as_avg) if r.as_avg is not None else None,
        )
        for r in result.all()
    ]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

History = dict[str, list[PlayerSeason]]
Predictions = dict[str, float]


def _safe_cv(std: float, avg: float) -> float:
    return std / avg if avg > 0 else 1.0


def _pos_mean(data: list[PlayerSeason], pos: str) -> float:
    vals = [ps.avg_pts for ps in data if ps.position == pos and ps.avg_pts > 0]
    return statistics.mean(vals) if vals else 3.0


# --- PRESEASON MODELS (history only) ---

def m_simple_avg(h: History, targets: set[str], **_kw: object) -> Predictions:
    """A: Last season average."""
    return {s: h[s][-1].avg_pts for s in targets if h.get(s)}


def m_weighted_career(h: History, targets: set[str], **_kw: object) -> Predictions:
    """B: Weighted 50/30/20 last 3 seasons."""
    weights = [0.50, 0.30, 0.20]
    preds = {}
    for slug in targets:
        seasons = h.get(slug, [])
        if not seasons:
            continue
        recent = seasons[-3:]
        w = weights[:len(recent)]
        tw = sum(w)
        preds[slug] = sum(s.avg_pts * wi / tw for s, wi in zip(reversed(recent), w))
    return preds


def m_career_trend(h: History, targets: set[str], **_kw: object) -> Predictions:
    """C: Career avg + trend."""
    preds = {}
    for slug in targets:
        seasons = h.get(slug, [])
        if not seasons:
            continue
        avg = statistics.mean(s.avg_pts for s in seasons)
        if len(seasons) >= 2 and seasons[-2].avg_pts > 0:
            trend = (seasons[-1].avg_pts - seasons[-2].avg_pts) / seasons[-2].avg_pts
            preds[slug] = avg * (1 + trend * 0.5)
        else:
            preds[slug] = avg
    return preds


def m_regression(h: History, targets: set[str], all_data: list[PlayerSeason] | None = None, **_kw: object) -> Predictions:
    """D: Regression to positional mean."""
    all_data = all_data or []
    preds = {}
    for slug in targets:
        seasons = h.get(slug, [])
        if not seasons:
            continue
        avg = statistics.mean(s.avg_pts for s in seasons)
        pos = seasons[-1].position
        pm = _pos_mean(all_data, pos)
        preds[slug] = avg * 0.6 + pm * 0.4
    return preds


def m_marca_as(h: History, targets: set[str], **_kw: object) -> Predictions:
    """E: Career avg weighted by Marca + AS trend."""
    all_marca = [s.marca_avg for ss in h.values() for s in ss if s.marca_avg]
    all_as = [s.as_avg for ss in h.values() for s in ss if s.as_avg]
    g_marca = statistics.mean(all_marca) if all_marca else 1.0
    g_as = statistics.mean(all_as) if all_as else 1.0

    preds = {}
    for slug in targets:
        seasons = h.get(slug, [])
        if not seasons:
            continue
        avg = statistics.mean(s.avg_pts for s in seasons)
        last = seasons[-1]
        factor = 1.0
        if last.marca_avg and g_marca > 0:
            factor *= 1 + (last.marca_avg / g_marca - 1) * 0.15
        if last.as_avg and g_as > 0:
            factor *= 1 + (last.as_avg / g_as - 1) * 0.15
        preds[slug] = avg * factor
    return preds


def m_availability(h: History, targets: set[str], **_kw: object) -> Predictions:
    """F: Per-game avg × expected games."""
    preds = {}
    for slug in targets:
        seasons = h.get(slug, [])
        if not seasons:
            continue
        avg = statistics.mean(s.avg_pts for s in seasons)
        avail = statistics.mean(s.games / 38 for s in seasons)
        preds[slug] = avg * avail  # per-game adjusted by availability
    return preds


def m_composite(h: History, targets: set[str], all_data: list[PlayerSeason] | None = None, **_kw: object) -> Predictions:
    """G: Composite — career + trend + regression + marca/AS + availability + consistency."""
    all_data = all_data or []
    all_marca = [s.marca_avg for ss in h.values() for s in ss if s.marca_avg]
    all_as = [s.as_avg for ss in h.values() for s in ss if s.as_avg]
    g_marca = statistics.mean(all_marca) if all_marca else 1.0
    g_as = statistics.mean(all_as) if all_as else 1.0

    weights = [0.50, 0.30, 0.20]
    preds = {}
    for slug in targets:
        seasons = h.get(slug, [])
        if not seasons:
            continue

        # Weighted career
        recent = seasons[-3:]
        w = weights[:len(recent)]
        tw = sum(w)
        base = sum(s.avg_pts * wi / tw for s, wi in zip(reversed(recent), w))

        # Trend
        if len(seasons) >= 2 and seasons[-2].avg_pts > 0:
            trend = (seasons[-1].avg_pts - seasons[-2].avg_pts) / seasons[-2].avg_pts
            base *= 1 + trend * 0.25

        # Regression to mean
        pos = seasons[-1].position
        pm = _pos_mean(all_data, pos)
        base = base * 0.7 + pm * 0.3

        # Marca/AS
        last = seasons[-1]
        if last.marca_avg and g_marca > 0:
            base *= 1 + (last.marca_avg / g_marca - 1) * 0.1
        if last.as_avg and g_as > 0:
            base *= 1 + (last.as_avg / g_as - 1) * 0.1

        # Availability
        avail = statistics.mean(s.games / 38 for s in seasons)
        base *= 0.7 + avail * 0.3  # partial adjustment, not full multiply

        # Consistency
        cv = _safe_cv(seasons[-1].std_pts, seasons[-1].avg_pts)
        base *= 1 - cv * 0.15

        preds[slug] = base
    return preds


# --- WINTER DRAFT MODELS (history + partial current season) ---

def m_winter_simple(h: History, targets: set[str], partial: dict[str, PlayerPartial] | None = None, **_kw: object) -> Predictions:
    """W1: Simple blend — partial season only (if available), fallback to career."""
    partial = partial or {}
    career = m_simple_avg(h, targets)
    preds = {}
    for slug in targets:
        p = partial.get(slug)
        c = career.get(slug)
        if p and c:
            # Weight by games played in current season
            w_current = min(0.7, p.games / 25)
            preds[slug] = c * (1 - w_current) + p.avg_pts * w_current
        elif p:
            preds[slug] = p.avg_pts
        elif c:
            preds[slug] = c
    return preds


def m_winter_marca_trend(h: History, targets: set[str], partial: dict[str, PlayerPartial] | None = None, **_kw: object) -> Predictions:
    """W2: Winter blend with Marca/AS trend from current season vs career."""
    partial = partial or {}
    base_preds = m_winter_simple(h, targets, partial=partial)
    preds = {}
    for slug in targets:
        base = base_preds.get(slug)
        if not base:
            continue
        p = partial.get(slug)
        seasons = h.get(slug, [])
        if p and p.marca_avg and seasons:
            career_marca = statistics.mean(s.marca_avg for s in seasons if s.marca_avg) if any(s.marca_avg for s in seasons) else None
            if career_marca and career_marca > 0:
                trend = p.marca_avg / career_marca
                base *= 1 + (trend - 1) * 0.2
        preds[slug] = base
    return preds


def m_winter_composite(h: History, targets: set[str], partial: dict[str, PlayerPartial] | None = None, all_data: list[PlayerSeason] | None = None, **_kw: object) -> Predictions:
    """W3: Full composite for winter — career + current + marca/AS + availability."""
    partial = partial or {}
    all_data = all_data or []
    all_marca = [s.marca_avg for ss in h.values() for s in ss if s.marca_avg]
    g_marca = statistics.mean(all_marca) if all_marca else 1.0

    weights = [0.50, 0.30, 0.20]
    preds = {}
    for slug in targets:
        seasons = h.get(slug, [])
        p = partial.get(slug)
        if not seasons and not p:
            continue

        # Career base
        if seasons:
            recent = seasons[-3:]
            w = weights[:len(recent)]
            tw = sum(w)
            career = sum(s.avg_pts * wi / tw for s, wi in zip(reversed(recent), w))
        else:
            career = None

        # Current season
        current = p.avg_pts if p else None

        # Blend
        if career and current and p:
            w_curr = min(0.7, p.games / 25)
            base = career * (1 - w_curr) + current * w_curr
        elif current:
            base = current
        elif career:
            base = career
        else:
            continue

        # Trend from current Marca vs career Marca
        if p and p.marca_avg and seasons:
            career_marca_vals = [s.marca_avg for s in seasons if s.marca_avg]
            if career_marca_vals:
                cm = statistics.mean(career_marca_vals)
                if cm > 0:
                    base *= 1 + (p.marca_avg / cm - 1) * 0.15

        # Regression to mean
        pos = seasons[-1].position if seasons else "MED"
        pm = _pos_mean(all_data, pos)
        base = base * 0.75 + pm * 0.25

        # Availability from current season
        if p and p.games > 0:
            config_start = 6  # approximate
            possible_games = max(p.games, 10)
            avail = p.games / possible_games
            base *= 0.8 + avail * 0.2

        preds[slug] = base
    return preds


def m_second_half_weighted(h: History, targets: set[str], **_kw: object) -> Predictions:
    """H: Weight second half of season more (players who finish strong carry into next season)."""
    preds = {}
    for slug in targets:
        seasons = h.get(slug, [])
        if not seasons:
            continue
        last = seasons[-1]
        if last.second_half_avg > 0 and last.first_half_avg > 0:
            # 60% second half, 40% first half — finishing form predicts next season start
            preds[slug] = last.second_half_avg * 0.6 + last.first_half_avg * 0.4
        else:
            preds[slug] = last.avg_pts
    return preds


def m_productivity_rate(h: History, targets: set[str], **_kw: object) -> Predictions:
    """I: Goals+assists per 90 min as proxy for attacking contribution."""
    preds = {}
    for slug in targets:
        seasons = h.get(slug, [])
        if not seasons:
            continue
        last = seasons[-1]
        base = last.avg_pts
        if last.minutes > 500:
            ga_per90 = ((last.goals + last.assists) / last.minutes) * 90 if last.minutes > 0 else 0
            # Boost players with high G+A rate (more likely to sustain)
            if ga_per90 > 0.5:
                base *= 1 + (ga_per90 - 0.5) * 0.3
        preds[slug] = base
    return preds


def m_discipline_adj(h: History, targets: set[str], **_kw: object) -> Predictions:
    """J: Penalize yellow-card-prone players (cards = negative pts)."""
    preds = {}
    for slug in targets:
        seasons = h.get(slug, [])
        if not seasons:
            continue
        last = seasons[-1]
        base = last.avg_pts
        if last.games > 0:
            yellow_rate = last.yellows / last.games
            # Avg ~0.15 yellows/game; penalize above-average
            if yellow_rate > 0.2:
                base *= 1 - (yellow_rate - 0.2) * 0.5
        preds[slug] = base
    return preds


def m_minutes_stability(h: History, targets: set[str], **_kw: object) -> Predictions:
    """K: Favor players with stable high minutes across seasons (undisputed starters)."""
    preds = {}
    for slug in targets:
        seasons = h.get(slug, [])
        if not seasons:
            continue
        career_avg = statistics.mean(s.avg_pts for s in seasons)
        # Minutes stability: high games_45min across seasons = reliable starter
        starter_rates = [s.games_45min / max(s.games, 1) for s in seasons]
        avg_starter = statistics.mean(starter_rates)
        # Boost reliable starters, penalize rotation players
        preds[slug] = career_avg * (0.8 + avg_starter * 0.4)  # range: 0.8x to 1.2x
    return preds


def m_marca_as_absolute(h: History, targets: set[str], **_kw: object) -> Predictions:
    """L: Pure Marca + AS rating prediction (media likes good players)."""
    preds = {}
    for slug in targets:
        seasons = h.get(slug, [])
        if not seasons:
            continue
        last = seasons[-1]
        # Combine marca and AS into a single quality score
        marca = last.marca_avg or 1.0
        as_val = last.as_avg or 1.0
        media_score = marca * 0.5 + as_val * 0.5
        # Use media score as direct predictor (scaled to pts range)
        preds[slug] = last.avg_pts * 0.6 + media_score * 2.5 * 0.4
    return preds


def m_floor_ceiling(h: History, targets: set[str], **_kw: object) -> Predictions:
    """M: Optimize for floor (worst case) — pick players with high minimums."""
    preds = {}
    for slug in targets:
        seasons = h.get(slug, [])
        if not seasons:
            continue
        last = seasons[-1]
        # p10-like: avg minus 1.3 std_dev (approximates 10th percentile)
        floor = last.avg_pts - 1.3 * last.std_pts
        # Weight 60% floor + 40% avg (prioritize safety)
        preds[slug] = max(floor, 0) * 0.6 + last.avg_pts * 0.4
    return preds


def m_ceiling(h: History, targets: set[str], **_kw: object) -> Predictions:
    """N: Optimize for ceiling (best case) — pick boom players."""
    preds = {}
    for slug in targets:
        seasons = h.get(slug, [])
        if not seasons:
            continue
        last = seasons[-1]
        ceiling = last.avg_pts + 1.3 * last.std_pts
        preds[slug] = last.avg_pts * 0.4 + ceiling * 0.6
    return preds


def m_bayesian_blend(h: History, targets: set[str], all_data: list[PlayerSeason] | None = None, **_kw: object) -> Predictions:
    """O: Bayesian shrinkage — pull extreme players toward position mean proportional to sample size."""
    all_data = all_data or []
    preds = {}
    for slug in targets:
        seasons = h.get(slug, [])
        if not seasons:
            continue
        total_games = sum(s.games for s in seasons)
        career_avg = statistics.mean(s.avg_pts for s in seasons)
        pos = seasons[-1].position
        pm = _pos_mean(all_data, pos)
        # More games = trust player avg more; fewer = shrink to position mean
        # k = "confidence" parameter; typical ~30 games for full trust
        k = 30
        shrinkage = total_games / (total_games + k)
        preds[slug] = career_avg * shrinkage + pm * (1 - shrinkage)
    return preds


def m_marca_stable_team(h: History, targets: set[str], **_kw: object) -> Predictions:
    """P: Marca/AS weighted, boosted for same-team stability across seasons.

    Core insight: players with good Marca/AS who stayed at the same team
    are the most predictable. Team changers are discounted.
    """
    all_marca = [s.marca_avg for ss in h.values() for s in ss if s.marca_avg]
    all_as = [s.as_avg for ss in h.values() for s in ss if s.as_avg]
    g_marca = statistics.mean(all_marca) if all_marca else 1.0
    g_as = statistics.mean(all_as) if all_as else 1.0

    preds = {}
    for slug in targets:
        seasons = h.get(slug, [])
        if not seasons:
            continue
        last = seasons[-1]

        # Base: career avg weighted
        if len(seasons) >= 2:
            base = seasons[-1].avg_pts * 0.6 + seasons[-2].avg_pts * 0.4
        else:
            base = last.avg_pts

        # Marca/AS factor (strong weight — your intuition)
        media_factor = 1.0
        if last.marca_avg and g_marca > 0:
            media_factor *= 1 + (last.marca_avg / g_marca - 1) * 0.25
        if last.as_avg and g_as > 0:
            media_factor *= 1 + (last.as_avg / g_as - 1) * 0.25
        base *= media_factor

        # Same team stability bonus
        if len(seasons) >= 2:
            same_team = seasons[-1].team_name == seasons[-2].team_name
            if same_team:
                base *= 1.05  # 5% bonus for stability
            else:
                base *= 0.90  # 10% penalty for team change (adaptation risk)

        # High games = more reliable
        if last.games >= 25:
            base *= 1.03  # slight bonus for high-sample players

        preds[slug] = base
    return preds


def m_marca_plus_2ndhalf(h: History, targets: set[str], **_kw: object) -> Predictions:
    """Q: Marca/AS + second half form + same team. The 'complete intuition' model."""
    all_marca = [s.marca_avg for ss in h.values() for s in ss if s.marca_avg]
    all_as = [s.as_avg for ss in h.values() for s in ss if s.as_avg]
    g_marca = statistics.mean(all_marca) if all_marca else 1.0
    g_as = statistics.mean(all_as) if all_as else 1.0

    preds = {}
    for slug in targets:
        seasons = h.get(slug, [])
        if not seasons:
            continue
        last = seasons[-1]

        # Use second half avg as base (finishing form = next season predictor)
        if last.second_half_avg > 0:
            base = last.second_half_avg * 0.55 + last.avg_pts * 0.45
        else:
            base = last.avg_pts

        # Marca/AS quality signal
        if last.marca_avg and g_marca > 0:
            base *= 1 + (last.marca_avg / g_marca - 1) * 0.2
        if last.as_avg and g_as > 0:
            base *= 1 + (last.as_avg / g_as - 1) * 0.2

        # Team stability
        if len(seasons) >= 2 and seasons[-1].team_name != seasons[-2].team_name:
            base *= 0.92  # discount for team change

        # Availability
        starter_pct = last.games_45min / max(last.games, 1)
        if starter_pct < 0.7:
            base *= 0.9 + starter_pct * 0.1  # slight penalty for rotation

        preds[slug] = base
    return preds


def m_team_quality(h: History, targets: set[str], all_data: list[PlayerSeason] | None = None, **_kw: object) -> Predictions:
    """R: Adjust by team fantasy strength (good teams boost all players)."""
    all_data = all_data or []
    # Compute team avg per season (latest season in training data)
    team_avgs: dict[str, float] = defaultdict(list)
    for ps in all_data:
        if ps.team_name:
            team_avgs[ps.team_name].append(ps.avg_pts)
    team_mean = {t: statistics.mean(v) for t, v in team_avgs.items() if v}
    global_mean = statistics.mean(team_mean.values()) if team_mean else 3.0

    preds = {}
    for slug in targets:
        seasons = h.get(slug, [])
        if not seasons:
            continue
        last = seasons[-1]
        base = last.avg_pts
        # Boost/penalize based on team quality
        tm = team_mean.get(last.team_name, global_mean)
        team_factor = tm / global_mean if global_mean > 0 else 1.0
        preds[slug] = base * (0.85 + team_factor * 0.15)
    return preds


def m_median_based(h: History, targets: set[str], **_kw: object) -> Predictions:
    """S: Use median pts instead of mean (robust to outliers/big games)."""
    # We don't have per-game data in PlayerSeason, approximate:
    # median ≈ avg - 0.2 * std for right-skewed distributions (typical in fantasy)
    preds = {}
    for slug in targets:
        seasons = h.get(slug, [])
        if not seasons:
            continue
        last = seasons[-1]
        approx_median = last.avg_pts - 0.2 * last.std_pts
        preds[slug] = max(approx_median, 0)
    return preds


def m_last10_momentum(h: History, targets: set[str], **_kw: object) -> Predictions:
    """T: Weight second half MORE aggressively (last 10 games = next season predictor)."""
    preds = {}
    for slug in targets:
        seasons = h.get(slug, [])
        if not seasons:
            continue
        last = seasons[-1]
        # second_half_avg is J20-J38, which is roughly last 18-19 games
        if last.second_half_avg > 0:
            preds[slug] = last.second_half_avg  # pure finishing form
        else:
            preds[slug] = last.avg_pts
    return preds


def m_ensemble_top3(h: History, targets: set[str], all_data: list[PlayerSeason] | None = None, **_kw: object) -> Predictions:
    """U: Average of 3 best preseason models (A + H + I)."""
    p_a = m_simple_avg(h, targets)
    p_h = m_second_half_weighted(h, targets)
    p_i = m_productivity_rate(h, targets)
    preds = {}
    for slug in targets:
        vals = [p for p in [p_a.get(slug), p_h.get(slug), p_i.get(slug)] if p is not None]
        if vals:
            preds[slug] = statistics.mean(vals)
    return preds


def m_ensemble_diverse(h: History, targets: set[str], all_data: list[PlayerSeason] | None = None, **_kw: object) -> Predictions:
    """V: Average of diverse models (A=precision + K=safety + C=trend + H=form)."""
    p_a = m_simple_avg(h, targets)
    p_k = m_minutes_stability(h, targets)
    p_c = m_career_trend(h, targets)
    p_h = m_second_half_weighted(h, targets)
    preds = {}
    for slug in targets:
        vals = [p for p in [p_a.get(slug), p_k.get(slug), p_c.get(slug), p_h.get(slug)] if p is not None]
        if vals:
            preds[slug] = statistics.mean(vals)
    return preds


def m_position_specific(h: History, targets: set[str], all_data: list[PlayerSeason] | None = None, **_kw: object) -> Predictions:
    """W: Different formula per position (POR=consistency, DEF=clean sheets, MED/DEL=goals)."""
    preds = {}
    for slug in targets:
        seasons = h.get(slug, [])
        if not seasons:
            continue
        last = seasons[-1]
        pos = last.position

        if pos == "POR":
            # Goalkeepers: consistency matters most (clean sheets = stable pts)
            cv = _safe_cv(last.std_pts, last.avg_pts)
            preds[slug] = last.avg_pts * (1.1 - cv * 0.3)  # low CV = bonus
        elif pos == "DEF":
            # Defenders: availability + base avg (clean sheet pts come from playing)
            avail = last.games_45min / max(last.games, 1)
            preds[slug] = last.avg_pts * (0.85 + avail * 0.3)
        elif pos == "DEL":
            # Forwards: goals per 90 is the key differentiator
            if last.minutes > 500:
                g_per90 = (last.goals / last.minutes) * 90
                preds[slug] = last.avg_pts * (0.9 + g_per90 * 0.3)
            else:
                preds[slug] = last.avg_pts
        else:  # MED
            # Midfielders: assists + goals + media ratings (most balanced)
            if last.minutes > 500:
                ga_per90 = ((last.goals + last.assists) / last.minutes) * 90
                preds[slug] = last.avg_pts * (0.9 + ga_per90 * 0.2)
            else:
                preds[slug] = last.avg_pts
    return preds


def m_marca_only_experienced(h: History, targets: set[str], **_kw: object) -> Predictions:
    """X: For players with 25+ games, trust Marca/AS heavily. For others, fallback to avg."""
    all_marca = [s.marca_avg for ss in h.values() for s in ss if s.marca_avg and s.games >= 25]
    all_as = [s.as_avg for ss in h.values() for s in ss if s.as_avg and s.games >= 25]
    g_marca = statistics.mean(all_marca) if all_marca else 1.0
    g_as = statistics.mean(all_as) if all_as else 1.0

    preds = {}
    for slug in targets:
        seasons = h.get(slug, [])
        if not seasons:
            continue
        last = seasons[-1]

        if last.games >= 25 and last.marca_avg and last.as_avg:
            # High sample: trust media ratings strongly
            marca_norm = last.marca_avg / g_marca if g_marca else 1
            as_norm = last.as_avg / g_as if g_as else 1
            media_score = (marca_norm + as_norm) / 2
            # 50% avg + 50% media-adjusted avg
            preds[slug] = last.avg_pts * 0.5 + last.avg_pts * media_score * 0.5
        else:
            # Low sample: just avg
            preds[slug] = last.avg_pts
    return preds


PRESEASON_MODELS = {
    "A_simple_avg": m_simple_avg,
    "B_weighted_career": m_weighted_career,
    "C_career_trend": m_career_trend,
    "D_regression_mean": m_regression,
    "E_marca_as": m_marca_as,
    "F_availability": m_availability,
    "G_composite": m_composite,
    "H_2nd_half": m_second_half_weighted,
    "I_productivity": m_productivity_rate,
    "J_discipline": m_discipline_adj,
    "K_minutes_stab": m_minutes_stability,
    "L_marca_absolute": m_marca_as_absolute,
    "M_floor_safe": m_floor_ceiling,
    "N_ceiling_boom": m_ceiling,
    "O_bayesian": m_bayesian_blend,
    "P_marca_stable": m_marca_stable_team,
    "Q_marca_2ndhalf": m_marca_plus_2ndhalf,
    "R_team_quality": m_team_quality,
    "S_median": m_median_based,
    "T_last10_pure": m_last10_momentum,
    "U_ensemble_top3": m_ensemble_top3,
    "V_ensemble_div": m_ensemble_diverse,
    "W_pos_specific": m_position_specific,
    "X_marca_expert": m_marca_only_experienced,
}

WINTER_MODELS = {
    "A_simple_avg": m_simple_avg,  # baseline: only career
    "W1_winter_simple": m_winter_simple,
    "W2_winter_marca": m_winter_marca_trend,
    "W3_winter_composite": m_winter_composite,
}


# ---------------------------------------------------------------------------
# Draft simulation + evaluation
# ---------------------------------------------------------------------------


def simulate_draft(preds: Predictions, actual: dict[str, PlayerSeason]) -> list[float]:
    ranked = sorted(preds.keys(), key=lambda s: preds.get(s, 0), reverse=True)
    teams: list[list[str]] = [[] for _ in range(DRAFT_PARTICIPANTS)]
    order = list(range(DRAFT_PARTICIPANTS))
    available = list(ranked)

    for rnd in range(DRAFT_PICKS):
        if rnd % 2 == 1:
            order = list(reversed(order))
        for idx in order:
            if available and len(teams[idx]) < DRAFT_PICKS:
                teams[idx].append(available.pop(0))

    return [sum(actual[s].total_pts for s in t if s in actual) for t in teams]


def random_baseline(actual: dict[str, PlayerSeason]) -> float:
    slugs = list(actual.keys())
    scores = []
    for _ in range(RANDOM_TRIALS):
        random.shuffle(slugs)
        scores.append(sum(actual[s].total_pts for s in slugs[:DRAFT_PICKS]))
    return statistics.mean(scores)


@dataclass
class Result:
    mae: float = 0
    spearman: float = 0
    top_n_pct: float = 0
    draft_avg: float = 0
    draft_vs_rand: float = 0
    bust_pct: float = 0
    n: int = 0


def evaluate(preds: Predictions, actual: dict[str, PlayerSeason], rand_base: float) -> Result:
    common = set(preds) & set(actual)
    if len(common) < 20:
        return Result()

    errors = [abs(preds[s] - actual[s].avg_pts) for s in common]
    pred_v = [preds[s] for s in common]
    act_v = [actual[s].avg_pts for s in common]
    rho, _ = scipy_stats.spearmanr(pred_v, act_v)

    top_n = min(26, len(common) // 3)
    pred_top = set(sorted(common, key=lambda s: preds[s], reverse=True)[:top_n])
    act_top = set(sorted(common, key=lambda s: actual[s].avg_pts, reverse=True)[:top_n])
    overlap = len(pred_top & act_top) / top_n

    draft = simulate_draft(preds, actual)
    median_act = statistics.median(act_v)
    top10 = sorted(common, key=lambda s: preds[s], reverse=True)[:10]
    busts = sum(1 for s in top10 if actual[s].avg_pts < median_act) / 10

    return Result(
        mae=round(statistics.mean(errors), 3),
        spearman=round(rho, 3),
        top_n_pct=round(overlap, 3),
        draft_avg=round(statistics.mean(draft), 1),
        draft_vs_rand=round(statistics.mean(draft) / rand_base, 3) if rand_base else 0,
        bust_pct=round(busts, 3),
        n=len(common),
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def run() -> dict:
    async with AsyncSessionLocal() as session:
        log.info("Loading data...")
        configs = await load_season_configs(session)
        all_data = await load_full_seasons(session)

        # Pre-load partial season data for winter draft windows
        partials: dict[int, dict[str, PlayerPartial]] = {}
        for sid, cfg in configs.items():
            max_md = cfg.matchday_winter - 1
            rows = await load_partial_season(session, sid, max_md)
            partials[sid] = {r.slug: r for r in rows}
            log.info("  Partial T%d (J≤%d): %d players", sid, max_md, len(rows))

    log.info("Loaded %d player-season records", len(all_data))

    by_slug: dict[str, list[PlayerSeason]] = defaultdict(list)
    for ps in all_data:
        by_slug[ps.slug].append(ps)
    for slug in by_slug:
        by_slug[slug].sort(key=lambda s: s.season_id)

    # Validation windows
    windows = [
        {"train": [5], "predict": 6},
        {"train": [5, 6], "predict": 7},
        {"train": [5, 6, 7], "predict": 8},
    ]

    all_results: list[dict] = []

    for window in windows:
        train_ids = set(window["train"])
        pred_id = window["predict"]
        pred_name = configs[pred_id].name
        train_names = [configs[i].name for i in sorted(train_ids)]

        log.info("\n=== Window: train=%s → predict=%s ===", train_names, pred_name)

        # Build history (train only)
        history: History = defaultdict(list)
        for slug, seasons in by_slug.items():
            for ps in seasons:
                if ps.season_id in train_ids:
                    history[slug].append(ps)

        # Actual results
        actual = {s: ps for slug, seasons in by_slug.items() for ps in seasons if ps.season_id == pred_id for s in [slug]}

        targets = set(actual) & set(history)
        rand_base = random_baseline(actual)

        log.info("  Players: %d actual, %d with history, random=%.0f", len(actual), len(targets), rand_base)

        train_data = [ps for ps in all_data if ps.season_id in train_ids]

        # --- PRESEASON DRAFT ---
        log.info("  --- PRESEASON DRAFT ---")
        pre_results = {}
        for name, fn in PRESEASON_MODELS.items():
            preds = fn(h=history, targets=targets, all_data=train_data)
            r = evaluate(preds, actual, rand_base)
            pre_results[name] = r
            log.info("    %-25s MAE=%.2f ρ=%.3f Top26=%.0f%% Draft=%.1fx Bust=%.0f%%",
                     name, r.mae, r.spearman, r.top_n_pct * 100, r.draft_vs_rand, r.bust_pct * 100)

        # --- WINTER DRAFT ---
        log.info("  --- WINTER DRAFT ---")
        partial = partials.get(pred_id, {})
        targets_winter = set(actual) & (set(history) | set(partial))
        rand_winter = random_baseline(actual)

        winter_results = {}
        for name, fn in WINTER_MODELS.items():
            preds = fn(h=history, targets=targets_winter, partial=partial, all_data=train_data)
            r = evaluate(preds, actual, rand_winter)
            winter_results[name] = r
            log.info("    %-25s MAE=%.2f ρ=%.3f Top26=%.0f%% Draft=%.1fx Bust=%.0f%%",
                     name, r.mae, r.spearman, r.top_n_pct * 100, r.draft_vs_rand, r.bust_pct * 100)

        all_results.append({
            "train": train_names,
            "predict": pred_name,
            "random_baseline": round(rand_base, 1),
            "preseason": {k: vars(v) for k, v in pre_results.items()},
            "winter": {k: vars(v) for k, v in winter_results.items()},
        })

    # Summary
    def _avg_metric(results: list[dict], section: str, model: str, metric: str) -> float:
        vals = [w[section][model][metric] for w in results if model in w[section]]
        return round(statistics.mean(vals), 3) if vals else 0

    summary = {"preseason": {}, "winter": {}}
    for name in PRESEASON_MODELS:
        summary["preseason"][name] = {
            "mae": _avg_metric(all_results, "preseason", name, "mae"),
            "spearman": _avg_metric(all_results, "preseason", name, "spearman"),
            "top_n": _avg_metric(all_results, "preseason", name, "top_n_pct"),
            "draft_vs_rand": _avg_metric(all_results, "preseason", name, "draft_vs_rand"),
            "bust": _avg_metric(all_results, "preseason", name, "bust_pct"),
        }
    for name in WINTER_MODELS:
        summary["winter"][name] = {
            "mae": _avg_metric(all_results, "winter", name, "mae"),
            "spearman": _avg_metric(all_results, "winter", name, "spearman"),
            "top_n": _avg_metric(all_results, "winter", name, "top_n_pct"),
            "draft_vs_rand": _avg_metric(all_results, "winter", name, "draft_vs_rand"),
            "bust": _avg_metric(all_results, "winter", name, "bust_pct"),
        }

    return {"windows": all_results, "summary": summary}


def print_summary(data: dict) -> None:
    for section in ["preseason", "winter"]:
        models = data["summary"][section]
        print(f"\n{'=' * 85}")
        print(f"  {section.upper()} DRAFT (avg across {len(data['windows'])} windows)")
        print(f"{'=' * 85}")
        print(f"  {'Model':<25} {'MAE':>5} {'Spearman':>9} {'Top26':>6} {'Draft/R':>8} {'Bust':>5}")
        print(f"  {'-' * 75}")
        for name, v in models.items():
            print(f"  {name:<25} {v['mae']:>5.2f} {v['spearman']:>9.3f} {v['top_n']*100:>5.0f}% {v['draft_vs_rand']:>7.2f}x {v['bust']*100:>4.0f}%")
        best_spearman = max(models, key=lambda m: models[m]["spearman"])
        best_draft = max(models, key=lambda m: models[m]["draft_vs_rand"])
        lowest_bust = min(models, key=lambda m: models[m]["bust"])
        print(f"  {'-' * 75}")
        print(f"  Best Spearman: {best_spearman}")
        print(f"  Best Draft:    {best_draft}")
        print(f"  Lowest Bust:   {lowest_bust}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", "-o", type=str, default=None)
    args = parser.parse_args()

    result = asyncio.run(run())
    print_summary(result)

    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        log.info("Written to %s", path)


if __name__ == "__main__":
    main()
