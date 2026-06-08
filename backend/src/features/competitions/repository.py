from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from src.shared.models.competition import Competition
from src.shared.models.competition_matchup import CompetitionMatchup
from src.shared.models.matchday import Matchday
from src.shared.models.participant import SeasonParticipant
from src.shared.models.score import ParticipantMatchdayScore
from src.shared.models.user import User


@dataclass
class StandingsRow:
    participant_id: int
    display_name: str
    draft_order: int
    group_label: str
    played: int
    wins: int
    draws: int
    losses: int
    rests: int
    points: int
    diff_avg: int
    pts_total_vpv: int


class CompetitionRepository:
    """Format-agnostic data access for competitions and matchups."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Competition CRUD
    # ------------------------------------------------------------------

    async def get(self, competition_id: int) -> Competition | None:
        return await self.session.get(Competition, competition_id)

    async def get_by_season_and_type(self, season_id: int, type_: str) -> Competition | None:
        stmt = select(Competition).where(
            Competition.season_id == season_id, Competition.type == type_
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_season(self, season_id: int) -> list[Competition]:
        stmt = (
            select(Competition)
            .where(Competition.season_id == season_id)
            .order_by(Competition.id.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def create(
        self,
        season_id: int,
        name: str,
        type_: str,
        config: dict[str, Any] | None,
    ) -> Competition:
        comp = Competition(
            season_id=season_id,
            name=name,
            type=type_,
            status="pending",
            config=config or {},
        )
        self.session.add(comp)
        await self.session.flush()
        return comp

    async def update_status(self, competition_id: int, status: str) -> None:
        await self.session.execute(
            update(Competition).where(Competition.id == competition_id).values(status=status)
        )

    async def update_config_patch(self, competition_id: int, patch: dict[str, Any]) -> None:
        """Merge ``patch`` into the JSONB ``config`` column.

        Reads-modify-writes the value in Python because the JSONB
        concatenation operator behaves differently across PG versions
        with our column shape. The session ensures we always work on a
        consistent copy."""
        comp = await self.get(competition_id)
        if comp is None:
            return
        merged = dict(comp.config or {})
        merged.update(patch)
        comp.config = merged
        self.session.add(comp)
        await self.session.flush()

    # ------------------------------------------------------------------
    # Matchup CRUD
    # ------------------------------------------------------------------

    async def insert_matchup(self, **kwargs: Any) -> CompetitionMatchup:
        row = CompetitionMatchup(**kwargs)
        self.session.add(row)
        await self.session.flush()
        return row

    async def count_matchups(self, competition_id: int, phase: str | None = None) -> int:
        stmt = select(func.count(CompetitionMatchup.id)).where(
            CompetitionMatchup.competition_id == competition_id
        )
        if phase is not None:
            stmt = stmt.where(CompetitionMatchup.phase == phase)
        return int((await self.session.execute(stmt)).scalar_one())

    async def count_unresolved_regular(self, competition_id: int) -> int:
        """Count regular-phase matchups that have not had their result
        recorded yet (excluding the ones whose ``participant_b_id`` is
        None — those are byes by construction).

        A draw is considered resolved: it has ``score_a`` and
        ``score_b`` set even though ``winner_participant_id`` is
        ``NULL``. So we filter by ``score_a IS NULL``."""
        stmt = select(func.count(CompetitionMatchup.id)).where(
            CompetitionMatchup.competition_id == competition_id,
            CompetitionMatchup.phase == "regular",
            CompetitionMatchup.score_a.is_(None),
            CompetitionMatchup.participant_b_id.isnot(None),
        )
        return int((await self.session.execute(stmt)).scalar_one())

    async def get_matchups_for_matchday(self, matchday_id: int) -> list[CompetitionMatchup]:
        stmt = select(CompetitionMatchup).where(CompetitionMatchup.matchday_id == matchday_id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_matchups_with_competition(self, competition_id: int) -> list[CompetitionMatchup]:
        stmt = (
            select(CompetitionMatchup)
            .where(CompetitionMatchup.competition_id == competition_id)
            .order_by(
                CompetitionMatchup.phase.asc(),
                CompetitionMatchup.round_number.asc(),
                CompetitionMatchup.id.asc(),
            )
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def update_matchup_result(
        self,
        matchup_id: int,
        score_a: int,
        score_b: int,
        winner_id: int | None,
    ) -> None:
        await self.session.execute(
            update(CompetitionMatchup)
            .where(CompetitionMatchup.id == matchup_id)
            .values(score_a=score_a, score_b=score_b, winner_participant_id=winner_id)
        )

    async def propagate_winner_to_feeders(self, source_matchup_id: int, winner_id: int) -> None:
        """Where another matchup references ``source_matchup_id`` as a
        feeder, write the winner into the corresponding participant
        slot. Idempotent: re-running with the same input is a no-op."""
        await self.session.execute(
            update(CompetitionMatchup)
            .where(CompetitionMatchup.feeder_a_id == source_matchup_id)
            .values(participant_a_id=winner_id)
        )
        await self.session.execute(
            update(CompetitionMatchup)
            .where(CompetitionMatchup.feeder_b_id == source_matchup_id)
            .values(participant_b_id=winner_id)
        )

    # ------------------------------------------------------------------
    # Helpers for the service
    # ------------------------------------------------------------------

    async def get_participant_ids(self, season_id: int) -> list[int]:
        stmt = (
            select(SeasonParticipant.id)
            .where(
                SeasonParticipant.season_id == season_id,
                SeasonParticipant.is_active.is_(True),
            )
            .order_by(SeasonParticipant.draft_order.asc().nulls_last())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_matchday_ids_in_range(self, season_id: int, start: int, end: int) -> list[int]:
        stmt = (
            select(Matchday.id)
            .where(
                Matchday.season_id == season_id,
                Matchday.number >= start,
                Matchday.number <= end,
            )
            .order_by(Matchday.number.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_matchday_ids_by_numbers(self, season_id: int, numbers: list[int]) -> list[int]:
        if not numbers:
            return []
        stmt = select(Matchday.id, Matchday.number).where(
            Matchday.season_id == season_id, Matchday.number.in_(numbers)
        )
        rows = (await self.session.execute(stmt)).all()
        # Preserve the order the caller asked for.
        lookup = {row.number: row.id for row in rows}
        return [lookup[n] for n in numbers if n in lookup]

    async def get_matchday_score(self, matchday_id: int, participant_id: int) -> int | None:
        stmt = select(ParticipantMatchdayScore.total_points).where(
            ParticipantMatchdayScore.matchday_id == matchday_id,
            ParticipantMatchdayScore.participant_id == participant_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_competition_for_matchup(self, matchup_id: int) -> Competition | None:
        stmt = (
            select(Competition)
            .join(
                CompetitionMatchup,
                CompetitionMatchup.competition_id == Competition.id,
            )
            .where(CompetitionMatchup.id == matchup_id)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    # ------------------------------------------------------------------
    # Standings aggregation
    # ------------------------------------------------------------------

    async def get_standings_rows(
        self, competition_id: int, group_label: str
    ) -> list[StandingsRow]:
        """Aggregate regular-phase results into per-participant rows.

        Implemented in Python over the materialised matchups (small
        N: 26 for v1, even fewer per group). Trading a tiny perf hit
        for a single readable query and easy debugging.
        """
        regular_stmt = select(CompetitionMatchup).where(
            CompetitionMatchup.competition_id == competition_id,
            CompetitionMatchup.phase == "regular",
            CompetitionMatchup.group_label == group_label,
        )
        matchups = list((await self.session.execute(regular_stmt)).scalars().all())

        # All participants that should appear (everyone in the group —
        # we infer from `participant_a/b_id` since the engine doesn't
        # store the group roster separately).
        participant_ids: set[int] = set()
        for m in matchups:
            if m.participant_a_id is not None:
                participant_ids.add(m.participant_a_id)
            if m.participant_b_id is not None:
                participant_ids.add(m.participant_b_id)

        if not participant_ids:
            return []

        # Look up display_name / draft_order in one shot.
        user_alias = aliased(User)
        info_stmt = (
            select(
                SeasonParticipant.id.label("pid"),
                user_alias.display_name,
                SeasonParticipant.draft_order,
            )
            .join(user_alias, user_alias.id == SeasonParticipant.user_id)
            .where(SeasonParticipant.id.in_(participant_ids))
        )
        info = {
            row.pid: (row.display_name, row.draft_order or 999)
            for row in (await self.session.execute(info_stmt)).all()
        }

        # Initialise tallies.
        stats: dict[int, dict[str, int]] = {
            pid: {
                "played": 0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
                "rests": 0,
                "points": 0,
                "diff_avg": 0,
                "pts_total_vpv": 0,
            }
            for pid in participant_ids
        }

        # We also need to count rests. A rest happens for a participant
        # whose group contains them BUT who has no matchup row in a
        # given round. We compute it by counting rounds in the group
        # and subtracting the matchups they appear in.
        rounds = sorted({m.round_number for m in matchups})

        for m in matchups:
            if m.score_a is None or m.score_b is None:
                # Unresolved cruce — count nothing yet.
                continue
            if m.participant_a_id is None or m.participant_b_id is None:
                continue
            stats[m.participant_a_id]["played"] += 1
            stats[m.participant_b_id]["played"] += 1
            stats[m.participant_a_id]["pts_total_vpv"] += m.score_a
            stats[m.participant_b_id]["pts_total_vpv"] += m.score_b
            stats[m.participant_a_id]["diff_avg"] += m.score_a - m.score_b
            stats[m.participant_b_id]["diff_avg"] += m.score_b - m.score_a
            if m.winner_participant_id is None:
                stats[m.participant_a_id]["draws"] += 1
                stats[m.participant_b_id]["draws"] += 1
                stats[m.participant_a_id]["points"] += 1
                stats[m.participant_b_id]["points"] += 1
            else:
                winner = m.winner_participant_id
                loser = m.participant_b_id if winner == m.participant_a_id else m.participant_a_id
                stats[winner]["wins"] += 1
                stats[loser]["losses"] += 1
                stats[winner]["points"] += 3

        # Rests = rounds in which the participant has no cruce.
        for pid in participant_ids:
            appears_in: set[int] = set()
            for m in matchups:
                if pid in (m.participant_a_id, m.participant_b_id):
                    appears_in.add(m.round_number)
            stats[pid]["rests"] = len(rounds) - len(appears_in)

        rows: list[StandingsRow] = []
        for pid, s in stats.items():
            name, draft_order = info.get(pid, (f"#{pid}", 999))
            rows.append(
                StandingsRow(
                    participant_id=pid,
                    display_name=name,
                    draft_order=draft_order,
                    group_label=group_label,
                    played=s["played"],
                    wins=s["wins"],
                    draws=s["draws"],
                    losses=s["losses"],
                    rests=s["rests"],
                    points=s["points"],
                    diff_avg=s["diff_avg"],
                    pts_total_vpv=s["pts_total_vpv"],
                )
            )
        return rows

    # ------------------------------------------------------------------
    # JOINed listings for the UI
    # ------------------------------------------------------------------

    async def list_matchups_with_names(self, competition_id: int) -> list[dict[str, Any]]:
        """List every matchup with participant display names and the
        matchday number. Single query, returns plain dicts for the
        schema layer to build ``MatchupEntry`` instances."""
        user_a = aliased(User)
        user_b = aliased(User)
        user_w = aliased(User)
        sp_a = aliased(SeasonParticipant)
        sp_b = aliased(SeasonParticipant)
        sp_w = aliased(SeasonParticipant)

        stmt = (
            select(
                CompetitionMatchup.id,
                CompetitionMatchup.phase,
                CompetitionMatchup.group_label,
                CompetitionMatchup.round_label,
                CompetitionMatchup.round_number,
                CompetitionMatchup.matchday_id,
                Matchday.number.label("matchday_number"),
                CompetitionMatchup.participant_a_id,
                user_a.display_name.label("participant_a_name"),
                CompetitionMatchup.participant_b_id,
                user_b.display_name.label("participant_b_name"),
                CompetitionMatchup.feeder_a_id,
                CompetitionMatchup.feeder_b_id,
                CompetitionMatchup.score_a,
                CompetitionMatchup.score_b,
                CompetitionMatchup.winner_participant_id,
                user_w.display_name.label("winner_name"),
            )
            .outerjoin(Matchday, Matchday.id == CompetitionMatchup.matchday_id)
            .outerjoin(sp_a, sp_a.id == CompetitionMatchup.participant_a_id)
            .outerjoin(user_a, user_a.id == sp_a.user_id)
            .outerjoin(sp_b, sp_b.id == CompetitionMatchup.participant_b_id)
            .outerjoin(user_b, user_b.id == sp_b.user_id)
            .outerjoin(sp_w, sp_w.id == CompetitionMatchup.winner_participant_id)
            .outerjoin(user_w, user_w.id == sp_w.user_id)
            .where(CompetitionMatchup.competition_id == competition_id)
            .order_by(
                CompetitionMatchup.phase.asc(),
                CompetitionMatchup.round_number.asc(),
                CompetitionMatchup.id.asc(),
            )
        )
        return [dict(r._mapping) for r in (await self.session.execute(stmt)).all()]


# Suppress unused-import warnings: these aliases are wired below.
_ = (and_, case)
