"""Closing a matchday: one definition of it, and a way to look before leaping.

Closing is the moment a jornada stops being provisional. It marks the matchday
finished, moves the season on, **generates the weekly payments** and evaluates
the achievements. Until now it was not an action anybody could take: the scraper
did it on its own, in one go, written out twice — once in ``scrape_matchday`` and
once in ``scrape_match_players`` — and the two copies had already drifted, since
only the second carried the knockout guard.

Nothing here changes what the automatic path does. It gives that path a single
definition, and gives an administrator two things he did not have: a way to ask
what state a jornada is in, and a way to close one by hand when the automation is
stuck — after being shown exactly what that would do.

Re-running is safe, and was already: ``generate_weekly_payments`` skips a matchday
that already has payments, ``evaluate_matchday`` lets the unique constraint absorb
duplicates, and the aggregation recomputes from the player rows. So the steps do
not need protecting; they needed naming, ordering and reporting.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.scraping.aggregation import ScoreAggregator
from src.features.scraping.repository import ScrapingRepository
from src.shared.models.matchday import Match
from src.shared.models.season import Season

logger = logging.getLogger(__name__)

Outcome = Literal["hecho", "ya_estaba", "bloqueado"]

# The six things closing does, in the order it does them.
STEP_STATS_OK = "Marcar la jornada con estadísticas completas"
STEP_FINISHED = "Marcar la jornada como terminada"
STEP_AGGREGATE = "Recalcular las puntuaciones de los participantes"
STEP_ADVANCE = "Avanzar la jornada actual de la temporada"
STEP_PAYMENTS = "Generar los pagos semanales"
STEP_ACHIEVEMENTS = "Evaluar los logros"
STEP_SCANNED = "Actualizar la última jornada procesada"


def expected_ko_pairings(season: object, matchday_number: int) -> int | None:
    """How many knockout ties the tournament config declares for this jornada.

    ``None`` for leagues, group stages and missing config. Moved here from
    ScrapingService: it guards against closing a knockout round whose fixtures
    are not all in the database yet, and that is a property of closing, not of
    scraping. It used to block only the advance, so a half-materialised round
    still paid out; now it blocks the close, which is the same reasoning as the
    no-result guard in #136.
    """
    if getattr(season, "kind", None) != "tournament":
        return None
    config = getattr(season, "tournament_config", None)
    if not isinstance(config, dict):
        return None
    knockout = config.get("knockout")
    if not isinstance(knockout, dict):
        return None
    for round_cfg in knockout.get("rounds", []):
        if not isinstance(round_cfg, dict):
            continue
        if int(round_cfg.get("matchday", 0)) == matchday_number:
            pairings = round_cfg.get("pairings") or []
            return len(pairings) if pairings else None
    return None


@dataclass(frozen=True)
class Step:
    name: str
    outcome: Outcome
    detail: str


@dataclass
class MatchdayStatus:
    """What a jornada looks like right now, and what stands between it and closing."""

    season_id: int
    matchday_number: int
    matchday_id: int
    status: str
    counts: bool
    stats_ok: bool
    deadline_at: str | None
    is_current: bool
    matches_total: int
    matches_counting: int
    matches_without_result: list[str] = field(default_factory=list)
    matches_without_stats: list[str] = field(default_factory=list)
    participants_total: int = 0
    lineups_missing: list[str] = field(default_factory=list)
    ratings_missing: int = 0
    last_scrape_at: str | None = None
    scrape_errors: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    @property
    def can_close(self) -> bool:
        return not self.blockers


@dataclass
class CloseReport:
    season_id: int
    matchday_number: int
    dry_run: bool
    closed: bool
    blockers: list[str]
    steps: list[Step]


class MatchdayClosing:
    """Reads the state of a jornada, and closes it.

    Uses ``ScrapingRepository`` for the mutations rather than restating them:
    they already live there, and duplicating six repository methods to avoid one
    import would be the very thing this module exists to undo.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ScrapingRepository(session)
        self._aggregator = ScoreAggregator(session)

    # -- reading ------------------------------------------------------------

    async def status(self, season_id: int, number: int) -> MatchdayStatus | None:
        season = await self.repo.get_season(season_id)
        matchday = await self.repo.get_matchday(season_id, number)
        if season is None or matchday is None:
            return None

        matches = await self.repo.get_matches_for_matchday(matchday.id)
        counting = [m for m in matches if m.counts]

        state = MatchdayStatus(
            season_id=season_id,
            matchday_number=number,
            matchday_id=matchday.id,
            status=matchday.status,
            counts=matchday.counts,
            stats_ok=matchday.stats_ok,
            deadline_at=matchday.deadline_at.isoformat() if matchday.deadline_at else None,
            is_current=season.matchday_current == number,
            matches_total=len(matches),
            matches_counting=len(counting),
            matches_without_result=[
                await self._label(m) for m in counting if m.home_score is None
            ],
            matches_without_stats=[await self._label(m) for m in counting if not m.stats_ok],
        )
        state.participants_total, state.lineups_missing = await self._lineups(
            season_id, matchday.id
        )
        state.ratings_missing = await self._ratings_missing(matchday.id)
        state.last_scrape_at, state.scrape_errors = await self._scraping(season_id, number)
        state.blockers = self._blockers(state, season, counting)
        return state

    def _blockers(self, state: MatchdayStatus, season: Season, counting: list[Match]) -> list[str]:
        """Why this jornada cannot be closed, in plain words."""
        blockers: list[str] = []
        if not counting:
            blockers.append("La jornada no tiene partidos que cuenten.")
        if state.matches_without_result:
            # The guard from PR #136, now stated once instead of implied twice.
            blockers.append(
                f"{len(state.matches_without_result)} partido(s) sin resultado: "
                + ", ".join(state.matches_without_result)
            )
        if state.matches_without_stats:
            blockers.append(
                f"{len(state.matches_without_stats)} partido(s) sin estadísticas: "
                + ", ".join(state.matches_without_stats)
            )
        if season.status == "finished" and not season.edit_unlocked:
            blockers.append("La temporada está cerrada. Desbloquea la edición para tocarla.")
        expected = expected_ko_pairings(season, state.matchday_number)
        if expected is not None and len(counting) < expected:
            blockers.append(
                f"Sólo {len(counting)} de {expected} eliminatorias están en la base. "
                "Faltan partidos por publicar en el calendario."
            )
        return blockers

    # -- closing ------------------------------------------------------------

    async def close(self, season_id: int, number: int, *, dry_run: bool) -> CloseReport:
        """Run the six steps, or report what running them would do.

        With ``dry_run`` nothing is written and the report says, for each step,
        whether it would act or find the work already done. That is the preview
        the audit asks for before an operation that pays money out.
        """
        state = await self.status(season_id, number)
        if state is None:
            return CloseReport(season_id, number, dry_run, False, ["La jornada no existe."], [])

        if state.blockers:
            return CloseReport(
                season_id,
                number,
                dry_run,
                False,
                state.blockers,
                [
                    Step(n, "bloqueado", "No se ejecuta: la jornada no puede cerrarse todavía.")
                    for n in self._step_names(state)
                ],
            )

        season = await self.repo.get_season(season_id)
        assert season is not None  # status() already proved it exists
        steps: list[Step] = []

        steps.append(await self._stats_ok(state, dry_run))
        steps.append(await self._finished(state, dry_run))
        steps.append(await self._aggregate(state, dry_run))
        steps.append(await self._advance(state, season, dry_run))
        steps.append(await self._payments(state, dry_run))
        steps.append(await self._achievements(state, dry_run))
        steps.append(await self._scanned(state, season, dry_run))

        if not dry_run:
            logger.info(
                "MatchdayClosing: closed season_id=%d J%d — %s",
                season_id,
                number,
                ", ".join(f"{s.name}: {s.outcome}" for s in steps),
            )
        return CloseReport(season_id, number, dry_run, True, [], steps)

    def _step_names(self, state: MatchdayStatus) -> list[str]:
        return [
            STEP_STATS_OK,
            STEP_FINISHED,
            STEP_AGGREGATE,
            STEP_ADVANCE,
            STEP_PAYMENTS,
            STEP_ACHIEVEMENTS,
            STEP_SCANNED,
        ]

    async def _stats_ok(self, state: MatchdayStatus, dry_run: bool) -> Step:
        if state.stats_ok:
            return Step(STEP_STATS_OK, "ya_estaba", "Ya estaba marcada.")
        if not dry_run:
            await self.repo.mark_matchday_stats_ok(state.matchday_id)
        return Step(STEP_STATS_OK, "hecho", "Todos los partidos que cuentan tienen estadísticas.")

    async def _finished(self, state: MatchdayStatus, dry_run: bool) -> Step:
        if state.status == "finished":
            return Step(STEP_FINISHED, "ya_estaba", "Ya estaba terminada.")
        if not dry_run:
            await self.repo.update_matchday_status(state.matchday_id, "finished")
        return Step(STEP_FINISHED, "hecho", f"Pasa de «{state.status}» a «finished».")

    async def _aggregate(self, state: MatchdayStatus, dry_run: bool) -> Step:
        # Always recomputed from the player rows, so it is never "ya estaba".
        if not dry_run:
            await self._aggregator.aggregate_matchday(state.matchday_id)
        return Step(
            STEP_AGGREGATE,
            "hecho",
            f"Recalcula la puntuación de {state.participants_total} participante(s).",
        )

    async def _advance(self, state: MatchdayStatus, season: Season, dry_run: bool) -> Step:
        if not state.is_current:
            return Step(
                STEP_ADVANCE,
                "ya_estaba",
                f"La temporada ya va por la J{season.matchday_current}.",
            )
        following = state.matchday_number + 1
        if following > (season.matchday_end or 38):
            return Step(STEP_ADVANCE, "ya_estaba", "Es la última jornada de la temporada.")
        if not dry_run:
            await self.repo.update_season_matchday_current(state.season_id, following)
        return Step(STEP_ADVANCE, "hecho", f"J{state.matchday_number} → J{following}.")

    async def _payments(self, state: MatchdayStatus, dry_run: bool) -> Step:
        from src.features.economy.service import EconomyService

        economy = EconomyService(self.session)
        season = await self.repo.get_season(state.season_id)
        if season is not None and not season.weekly_payments_enabled:
            return Step(STEP_PAYMENTS, "ya_estaba", "Esta temporada no tiene pagos semanales.")
        existing = await economy.repo.count_weekly_payments(state.matchday_id)
        if existing > 0:
            return Step(STEP_PAYMENTS, "ya_estaba", f"Ya tiene {existing} pago(s) generados.")
        if dry_run:
            return Step(STEP_PAYMENTS, "hecho", "Generaría los pagos semanales de esta jornada.")
        created = await economy.generate_weekly_payments(state.season_id, state.matchday_id)
        return Step(STEP_PAYMENTS, "hecho", f"Genera {created} pago(s).")

    async def _achievements(self, state: MatchdayStatus, dry_run: bool) -> Step:
        if dry_run:
            return Step(
                STEP_ACHIEVEMENTS,
                "hecho",
                "Evaluaría los logros. Repetirlo no los duplica.",
            )
        from src.features.achievements.engine import AchievementEngine

        summary = await AchievementEngine(self.session).evaluate_matchday(
            state.season_id, state.matchday_id, state.matchday_number
        )
        return Step(
            STEP_ACHIEVEMENTS,
            "hecho",
            f"Concede {summary.get('granted', 0)} logro(s).",
        )

    async def _scanned(self, state: MatchdayStatus, season: Season, dry_run: bool) -> Step:
        if (season.matchday_scanned or 0) >= state.matchday_number:
            return Step(STEP_SCANNED, "ya_estaba", "Ya estaba registrada como procesada.")
        if not dry_run:
            await self.repo.update_season_matchday_scanned(state.season_id, state.matchday_number)
        return Step(STEP_SCANNED, "hecho", f"Última procesada → J{state.matchday_number}.")

    # -- the readings the panel needs ---------------------------------------

    async def _label(self, match: Match) -> str:
        from src.shared.models.team import Team

        home = await self.session.get(Team, match.home_team_id)
        away = await self.session.get(Team, match.away_team_id)
        return f"{home.name if home else '?'} - {away.name if away else '?'}"

    async def _lineups(self, season_id: int, matchday_id: int) -> tuple[int, list[str]]:
        """Participants without a lineup for this matchday, by display name."""
        from src.shared.models.lineup import Lineup
        from src.shared.models.participant import SeasonParticipant
        from src.shared.models.user import User

        rows = (
            await self.session.execute(
                select(SeasonParticipant.id, User.display_name)
                .join(User, User.id == SeasonParticipant.user_id)
                .where(SeasonParticipant.season_id == season_id)
            )
        ).all()
        submitted = set(
            (
                await self.session.execute(
                    select(Lineup.participant_id).where(Lineup.matchday_id == matchday_id)
                )
            )
            .scalars()
            .all()
        )
        return len(rows), [name for pid, name in rows if pid not in submitted]

    async def _ratings_missing(self, matchday_id: int) -> int:
        """Player rows in played matches still without a Marca rating."""
        from src.shared.models.player_stat import PlayerStat

        return (
            await self.session.scalar(
                select(func.count())
                .select_from(PlayerStat)
                .join(Match, Match.id == PlayerStat.match_id)
                .where(
                    PlayerStat.matchday_id == matchday_id,
                    PlayerStat.played.is_(True),
                    Match.home_score.is_not(None),
                    PlayerStat.marca_rating.is_(None),
                )
            )
        ) or 0

    async def _scraping(self, season_id: int, number: int) -> tuple[str | None, list[str]]:
        from src.shared.models.scraping_log import ScrapingLog

        rows = (
            await self.session.execute(
                select(ScrapingLog.created_at, ScrapingLog.status, ScrapingLog.message)
                .where(
                    ScrapingLog.season_id == season_id,
                    ScrapingLog.matchday_number == number,
                )
                .order_by(ScrapingLog.created_at.desc())
                .limit(50)
            )
        ).all()
        if not rows:
            return None, []
        last = rows[0][0].isoformat() if rows[0][0] else None
        errors = [m or "sin detalle" for _, s, m in rows if s == "error"][:10]
        return last, errors
