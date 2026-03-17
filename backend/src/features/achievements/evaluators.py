from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.achievements.models import Achievement
from src.shared.models.draft import Draft, DraftPick
from src.shared.models.lineup import Lineup, LineupPlayer
from src.shared.models.matchday import Matchday
from src.shared.models.participant import SeasonParticipant
from src.shared.models.player_stat import PlayerStat
from src.shared.models.score import ParticipantMatchdayScore

logger = logging.getLogger(__name__)

# Type alias for an evaluator function
EvaluatorFn = Callable[
    [AsyncSession, int, int, int],
    Coroutine[Any, Any, list[Achievement]],
]


def _make_achievement(
    *,
    season_id: int,
    participant_id: int,
    matchday_id: int | None,
    achievement_key: str,
    tier: int = 1,
    metadata: dict[str, Any] | None = None,
) -> Achievement:
    return Achievement(
        season_id=season_id,
        participant_id=participant_id,
        matchday_id=matchday_id,
        achievement_key=achievement_key,
        tier=tier,
        metadata_=metadata,
        created_at=datetime.now(UTC),
    )


async def _get_counting_matchday_ids_up_to(
    session: AsyncSession,
    season_id: int,
    matchday_number: int,
) -> list[int]:
    """Return IDs of counting matchdays with number <= matchday_number."""
    stmt = (
        select(Matchday.id)
        .where(
            Matchday.season_id == season_id,
            Matchday.counts.is_(True),
            Matchday.number <= matchday_number,
        )
        .order_by(Matchday.number)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def _get_counting_matchday_ids_up_to_exclusive(
    session: AsyncSession,
    season_id: int,
    matchday_number: int,
) -> list[int]:
    """Return IDs of counting matchdays with number < matchday_number."""
    stmt = (
        select(Matchday.id)
        .where(
            Matchday.season_id == season_id,
            Matchday.counts.is_(True),
            Matchday.number < matchday_number,
        )
        .order_by(Matchday.number)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def _get_cumulative_ranks(
    session: AsyncSession,
    season_id: int,
    matchday_ids: list[int],
) -> dict[int, int]:
    """Compute cumulative point totals and derive ranks for all participants.

    Returns a dict of participant_id -> rank (1 = leader).
    Ties share the same rank (standard competition ranking).
    """
    if not matchday_ids:
        return {}

    stmt = (
        select(
            SeasonParticipant.id.label("participant_id"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            ParticipantMatchdayScore.matchday_id.in_(matchday_ids),
                            ParticipantMatchdayScore.total_points,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("total_points"),
        )
        .outerjoin(
            ParticipantMatchdayScore,
            ParticipantMatchdayScore.participant_id == SeasonParticipant.id,
        )
        .where(SeasonParticipant.season_id == season_id)
        .group_by(SeasonParticipant.id)
        .order_by(
            func.coalesce(
                func.sum(
                    case(
                        (
                            ParticipantMatchdayScore.matchday_id.in_(matchday_ids),
                            ParticipantMatchdayScore.total_points,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).desc()
        )
    )
    result = await session.execute(stmt)
    rows = result.all()

    ranks: dict[int, int] = {}
    prev_pts: int | None = None
    prev_rank = 0
    for i, row in enumerate(rows, start=1):
        pts = int(row.total_points)
        if pts == prev_pts:
            ranks[row.participant_id] = prev_rank
        else:
            ranks[row.participant_id] = i
            prev_rank = i
            prev_pts = pts
    return ranks


# ---------------------------------------------------------------------------
# Evaluators
# ---------------------------------------------------------------------------


async def evaluate_mvp_jornada(
    session: AsyncSession,
    season_id: int,
    matchday_id: int,
    matchday_number: int,
) -> list[Achievement]:
    """Award the participant with the highest score this matchday."""
    stmt = (
        select(
            ParticipantMatchdayScore.participant_id,
            ParticipantMatchdayScore.total_points,
        )
        .where(ParticipantMatchdayScore.matchday_id == matchday_id)
        .order_by(ParticipantMatchdayScore.total_points.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.one_or_none()
    if row is None:
        return []
    return [
        _make_achievement(
            season_id=season_id,
            participant_id=row.participant_id,
            matchday_id=matchday_id,
            achievement_key="mvp_jornada",
            metadata={"points": int(row.total_points)},
        )
    ]


async def evaluate_goleador(
    session: AsyncSession,
    season_id: int,
    matchday_id: int,
    matchday_number: int,
) -> list[Achievement]:
    """Award the participant whose XI scored the most goals this matchday."""
    stmt = (
        select(
            Lineup.participant_id,
            func.sum(PlayerStat.goals).label("total_goals"),
        )
        .join(LineupPlayer, LineupPlayer.lineup_id == Lineup.id)
        .join(
            PlayerStat,
            (PlayerStat.player_id == LineupPlayer.player_id)
            & (PlayerStat.matchday_id == matchday_id),
        )
        .where(Lineup.matchday_id == matchday_id)
        .group_by(Lineup.participant_id)
        .order_by(func.sum(PlayerStat.goals).desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.one_or_none()
    if row is None or int(row.total_goals or 0) == 0:
        return []
    return [
        _make_achievement(
            season_id=season_id,
            participant_id=row.participant_id,
            matchday_id=matchday_id,
            achievement_key="goleador",
            metadata={"goals": int(row.total_goals)},
        )
    ]


async def evaluate_muro(
    session: AsyncSession,
    season_id: int,
    matchday_id: int,
    matchday_number: int,
) -> list[Achievement]:
    """Award the participant with the highest clean-sheet points this matchday."""
    stmt = (
        select(
            Lineup.participant_id,
            func.sum(PlayerStat.pts_clean_sheet).label("total_cs"),
        )
        .join(LineupPlayer, LineupPlayer.lineup_id == Lineup.id)
        .join(
            PlayerStat,
            (PlayerStat.player_id == LineupPlayer.player_id)
            & (PlayerStat.matchday_id == matchday_id),
        )
        .where(Lineup.matchday_id == matchday_id)
        .group_by(Lineup.participant_id)
        .order_by(func.sum(PlayerStat.pts_clean_sheet).desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.one_or_none()
    if row is None or int(row.total_cs or 0) <= 0:
        return []
    return [
        _make_achievement(
            season_id=season_id,
            participant_id=row.participant_id,
            matchday_id=matchday_id,
            achievement_key="muro",
            metadata={"pts_clean_sheet": int(row.total_cs)},
        )
    ]


async def evaluate_remontada(
    session: AsyncSession,
    season_id: int,
    matchday_id: int,
    matchday_number: int,
) -> list[Achievement]:
    """Award participants who climbed 3+ positions in the cumulative standings."""
    ids_current = await _get_counting_matchday_ids_up_to(session, season_id, matchday_number)
    ids_previous = await _get_counting_matchday_ids_up_to_exclusive(
        session, season_id, matchday_number
    )

    if not ids_previous:
        # No previous data to compare against
        return []

    ranks_current = await _get_cumulative_ranks(session, season_id, ids_current)
    ranks_previous = await _get_cumulative_ranks(session, season_id, ids_previous)

    achievements = []
    for participant_id, rank_now in ranks_current.items():
        rank_before = ranks_previous.get(participant_id)
        if rank_before is None:
            continue
        climb = rank_before - rank_now  # positive = moved up
        if climb >= 3:
            achievements.append(
                _make_achievement(
                    season_id=season_id,
                    participant_id=participant_id,
                    matchday_id=matchday_id,
                    achievement_key="remontada",
                    metadata={
                        "positions_climbed": climb,
                        "rank_before": rank_before,
                        "rank_now": rank_now,
                    },
                )
            )
    return achievements


async def _get_last_n_counting_matchday_rankings(
    session: AsyncSession,
    season_id: int,
    matchday_number: int,
    n: int,
) -> dict[int, list[int]]:
    """Return dict of participant_id -> [ranking, ...] for the last N counting matchdays.

    The rankings are ordered from oldest to newest.
    Returns only participants that have exactly N scores available.
    """
    stmt = (
        select(Matchday.id, Matchday.number)
        .where(
            Matchday.season_id == season_id,
            Matchday.counts.is_(True),
            Matchday.number <= matchday_number,
        )
        .order_by(Matchday.number.desc())
        .limit(n)
    )
    result = await session.execute(stmt)
    recent_matchday_rows = result.all()

    if len(recent_matchday_rows) < n:
        return {}

    recent_ids = [row.id for row in recent_matchday_rows]

    stmt2 = (
        select(
            ParticipantMatchdayScore.participant_id,
            ParticipantMatchdayScore.matchday_id,
            ParticipantMatchdayScore.ranking,
        )
        .join(Matchday, ParticipantMatchdayScore.matchday_id == Matchday.id)
        .where(
            ParticipantMatchdayScore.matchday_id.in_(recent_ids),
            Matchday.season_id == season_id,
        )
    )
    result2 = await session.execute(stmt2)
    rows = result2.all()

    # Build a map: participant_id -> {matchday_id: ranking}
    by_participant: dict[int, dict[int, int]] = {}
    for row in rows:
        if row.ranking is None:
            continue
        by_participant.setdefault(row.participant_id, {})[row.matchday_id] = int(row.ranking)

    # Sort each participant's rankings from oldest to newest
    matchday_order = {row.id: i for i, row in enumerate(reversed(recent_matchday_rows))}
    result_map: dict[int, list[int]] = {}
    for pid, md_rankings in by_participant.items():
        if len(md_rankings) < n:
            continue
        sorted_rankings = [
            md_rankings[mid]
            for mid in sorted(md_rankings.keys(), key=lambda x: matchday_order.get(x, 0))
        ]
        result_map[pid] = sorted_rankings

    return result_map


async def evaluate_racha_ganadora(
    session: AsyncSession,
    season_id: int,
    matchday_id: int,
    matchday_number: int,
) -> list[Achievement]:
    """Award participants who ranked top-3 for N consecutive counting matchdays.

    Tiers: 7 (tier 3), 5 (tier 2), 3 (tier 1). Each participant gets only
    the highest tier they qualify for.
    """
    # tier_thresholds ordered highest to lowest: award first match only
    tier_thresholds = [(7, 3), (5, 2), (3, 1)]
    achievements = []
    awarded_participants: set[int] = set()

    for streak_len, tier in tier_thresholds:
        rankings_map = await _get_last_n_counting_matchday_rankings(
            session, season_id, matchday_number, streak_len
        )
        for participant_id, rankings in rankings_map.items():
            if participant_id in awarded_participants:
                continue
            if all(r <= 3 for r in rankings):
                achievements.append(
                    _make_achievement(
                        season_id=season_id,
                        participant_id=participant_id,
                        matchday_id=matchday_id,
                        achievement_key="racha_ganadora",
                        tier=tier,
                        metadata={"streak": streak_len, "rankings": rankings},
                    )
                )
                awarded_participants.add(participant_id)

    return achievements


async def evaluate_racha_perdedora(
    session: AsyncSession,
    season_id: int,
    matchday_id: int,
    matchday_number: int,
) -> list[Achievement]:
    """Award participants who ranked bottom-3 for N consecutive counting matchdays.

    Tiers: 7 (tier 3), 5 (tier 2), 3 (tier 1). Check highest first.
    """
    count_stmt = select(func.count(SeasonParticipant.id)).where(
        SeasonParticipant.season_id == season_id,
        SeasonParticipant.is_active.is_(True),
    )
    count_result = await session.execute(count_stmt)
    total_participants = int(count_result.scalar_one() or 0)
    if total_participants == 0:
        return []

    bottom_threshold = total_participants - 2  # ranking >= this means bottom 3

    tier_thresholds = [(7, 3), (5, 2), (3, 1)]
    achievements = []
    awarded_participants: set[int] = set()

    for streak_len, tier in tier_thresholds:
        rankings_map = await _get_last_n_counting_matchday_rankings(
            session, season_id, matchday_number, streak_len
        )
        for participant_id, rankings in rankings_map.items():
            if participant_id in awarded_participants:
                continue
            if all(r >= bottom_threshold for r in rankings):
                achievements.append(
                    _make_achievement(
                        season_id=season_id,
                        participant_id=participant_id,
                        matchday_id=matchday_id,
                        achievement_key="racha_perdedora",
                        tier=tier,
                        metadata={"streak": streak_len, "rankings": rankings},
                    )
                )
                awarded_participants.add(participant_id)

    return achievements


async def evaluate_imbatible(
    session: AsyncSession,
    season_id: int,
    matchday_id: int,
    matchday_number: int,
) -> list[Achievement]:
    """Award participants who ranked #1 for N consecutive counting matchdays.

    Tiers: 5 (tier 3), 3 (tier 2), 2 (tier 1). Check highest first.
    """
    tier_thresholds = [(5, 3), (3, 2), (2, 1)]
    achievements = []
    awarded_participants: set[int] = set()

    for streak_len, tier in tier_thresholds:
        rankings_map = await _get_last_n_counting_matchday_rankings(
            session, season_id, matchday_number, streak_len
        )
        for participant_id, rankings in rankings_map.items():
            if participant_id in awarded_participants:
                continue
            if all(r == 1 for r in rankings):
                achievements.append(
                    _make_achievement(
                        season_id=season_id,
                        participant_id=participant_id,
                        matchday_id=matchday_id,
                        achievement_key="imbatible",
                        tier=tier,
                        metadata={"streak": streak_len, "rankings": rankings},
                    )
                )
                awarded_participants.add(participant_id)

    return achievements


async def _get_cumulative_points_per_participant(
    session: AsyncSession,
    season_id: int,
    matchday_number: int,
) -> list[tuple[int, int]]:
    """Return list of (participant_id, cumulative_points) for counting matchdays up to now."""
    counting_ids = await _get_counting_matchday_ids_up_to(session, season_id, matchday_number)
    if not counting_ids:
        return []

    stmt = (
        select(
            SeasonParticipant.id.label("participant_id"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            ParticipantMatchdayScore.matchday_id.in_(counting_ids),
                            ParticipantMatchdayScore.total_points,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("total_points"),
        )
        .outerjoin(
            ParticipantMatchdayScore,
            ParticipantMatchdayScore.participant_id == SeasonParticipant.id,
        )
        .where(SeasonParticipant.season_id == season_id)
        .group_by(SeasonParticipant.id)
    )
    result = await session.execute(stmt)
    return [(row.participant_id, int(row.total_points)) for row in result.all()]


async def _get_existing_one_time_achievement_holders(
    session: AsyncSession,
    season_id: int,
    achievement_key: str,
) -> set[int]:
    """Return participant_ids that already have a non-repeatable achievement."""
    stmt = select(Achievement.participant_id).where(
        Achievement.season_id == season_id,
        Achievement.achievement_key == achievement_key,
    )
    result = await session.execute(stmt)
    return set(result.scalars().all())


async def evaluate_centenario(
    session: AsyncSession,
    season_id: int,
    matchday_id: int,
    matchday_number: int,
) -> list[Achievement]:
    """Award when a participant reaches 100 cumulative points (once per season)."""
    already_awarded = await _get_existing_one_time_achievement_holders(
        session, season_id, "centenario"
    )
    totals = await _get_cumulative_points_per_participant(session, season_id, matchday_number)
    achievements = []
    for participant_id, pts in totals:
        if participant_id not in already_awarded and pts >= 100:
            achievements.append(
                _make_achievement(
                    season_id=season_id,
                    participant_id=participant_id,
                    matchday_id=matchday_id,
                    achievement_key="centenario",
                    metadata={"total_points": pts},
                )
            )
    return achievements


async def evaluate_doble_centenario(
    session: AsyncSession,
    season_id: int,
    matchday_id: int,
    matchday_number: int,
) -> list[Achievement]:
    """Award when a participant reaches 200 cumulative points (once per season)."""
    already_awarded = await _get_existing_one_time_achievement_holders(
        session, season_id, "doble_centenario"
    )
    totals = await _get_cumulative_points_per_participant(session, season_id, matchday_number)
    achievements = []
    for participant_id, pts in totals:
        if participant_id not in already_awarded and pts >= 200:
            achievements.append(
                _make_achievement(
                    season_id=season_id,
                    participant_id=participant_id,
                    matchday_id=matchday_id,
                    achievement_key="doble_centenario",
                    metadata={"total_points": pts},
                )
            )
    return achievements


async def evaluate_triple_centenario(
    session: AsyncSession,
    season_id: int,
    matchday_id: int,
    matchday_number: int,
) -> list[Achievement]:
    """Award when a participant reaches 300 cumulative points (once per season)."""
    already_awarded = await _get_existing_one_time_achievement_holders(
        session, season_id, "triple_centenario"
    )
    totals = await _get_cumulative_points_per_participant(session, season_id, matchday_number)
    achievements = []
    for participant_id, pts in totals:
        if participant_id not in already_awarded and pts >= 300:
            achievements.append(
                _make_achievement(
                    season_id=season_id,
                    participant_id=participant_id,
                    matchday_id=matchday_id,
                    achievement_key="triple_centenario",
                    metadata={"total_points": pts},
                )
            )
    return achievements


async def evaluate_lider(
    session: AsyncSession,
    season_id: int,
    matchday_id: int,
    matchday_number: int,
) -> list[Achievement]:
    """Award the participant leading the cumulative standings each matchday."""
    counting_ids = await _get_counting_matchday_ids_up_to(session, season_id, matchday_number)
    if not counting_ids:
        return []

    ranks = await _get_cumulative_ranks(session, season_id, counting_ids)
    achievements = []
    for participant_id, rank in ranks.items():
        if rank == 1:
            achievements.append(
                _make_achievement(
                    season_id=season_id,
                    participant_id=participant_id,
                    matchday_id=matchday_id,
                    achievement_key="lider",
                )
            )
    return achievements


async def evaluate_robo_draft(
    session: AsyncSession,
    season_id: int,
    matchday_id: int,
    matchday_number: int,
) -> list[Achievement]:
    """Award late draft picks (round >= 20) that perform in the top 25% of all players.

    Only evaluated from matchday 10 onwards. Idempotent via uq_achievement.
    """
    if matchday_number < 10:
        return []

    # Get all draft_ids for this season (preseason draft)
    draft_stmt = select(Draft.id).where(
        Draft.season_id == season_id,
        Draft.phase == "preseason",
    )
    draft_result = await session.execute(draft_stmt)
    draft_ids = list(draft_result.scalars().all())
    if not draft_ids:
        return []

    # Get late picks (round >= 20)
    late_picks_stmt = select(
        DraftPick.player_id, DraftPick.participant_id, DraftPick.round_number
    ).where(
        DraftPick.draft_id.in_(draft_ids),
        DraftPick.round_number >= 20,
    )
    late_result = await session.execute(late_picks_stmt)
    late_picks = late_result.all()
    if not late_picks:
        return []

    # Get counting matchday IDs up to now
    counting_ids = await _get_counting_matchday_ids_up_to(session, season_id, matchday_number)
    if not counting_ids:
        return []

    # Compute season pts_total for all players with 5+ matchdays played
    player_pts_stmt = (
        select(
            PlayerStat.player_id,
            func.sum(PlayerStat.pts_total).label("season_pts"),
            func.count(PlayerStat.id).label("matchdays_played"),
        )
        .where(
            PlayerStat.matchday_id.in_(counting_ids),
        )
        .group_by(PlayerStat.player_id)
        .having(func.count(PlayerStat.id) >= 5)
    )
    pts_result = await session.execute(player_pts_stmt)
    pts_rows = pts_result.all()

    if not pts_rows:
        return []

    all_season_pts = sorted([int(row.season_pts) for row in pts_rows], reverse=True)
    player_pts_map = {row.player_id: int(row.season_pts) for row in pts_rows}

    # Determine the top-25% threshold
    top25_cutoff_index = max(0, len(all_season_pts) // 4 - 1)
    top25_threshold = all_season_pts[top25_cutoff_index] if all_season_pts else 0

    # Find already-awarded robo_draft for this season (keyed by matchday_id=None is not right;
    # robo_draft is repeatable but keyed on season+participant+matchday+key.
    # Since we use the current matchday_id, it's already handled by uq_achievement per matchday.
    # But we need to avoid re-awarding for the same player in prior matchdays.
    existing_stmt = select(Achievement.metadata_).where(
        Achievement.season_id == season_id,
        Achievement.achievement_key == "robo_draft",
    )
    existing_result = await session.execute(existing_stmt)
    already_awarded_player_ids: set[int] = set()
    for row in existing_result.all():
        meta = row[0]
        if meta and isinstance(meta, dict) and "player_id" in meta:
            already_awarded_player_ids.add(int(meta["player_id"]))

    achievements = []
    for pick in late_picks:
        player_id = pick.player_id
        if player_id in already_awarded_player_ids:
            continue
        season_pts = player_pts_map.get(player_id)
        if season_pts is None:
            continue
        if season_pts >= top25_threshold:
            achievements.append(
                _make_achievement(
                    season_id=season_id,
                    participant_id=pick.participant_id,
                    matchday_id=matchday_id,
                    achievement_key="robo_draft",
                    metadata={
                        "player_id": player_id,
                        "round_number": int(pick.round_number),
                        "season_pts": season_pts,
                        "top25_threshold": top25_threshold,
                    },
                )
            )
            already_awarded_player_ids.add(player_id)

    return achievements


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ALL_EVALUATORS: list[EvaluatorFn] = [
    evaluate_mvp_jornada,
    evaluate_goleador,
    evaluate_muro,
    evaluate_racha_ganadora,
    evaluate_racha_perdedora,
    evaluate_imbatible,
    evaluate_lider,
    evaluate_robo_draft,
]
