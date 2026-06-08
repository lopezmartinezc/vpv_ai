"""Format-agnostic playoff orchestration.

Every method dispatches the format-specific decisions to the plugin
registered under ``competitions.config.format_id``. To add a new
playoff format, drop a plugin in ``features/competitions/formats/``
and register it; this file does not need to change.
"""

from __future__ import annotations

import logging
import random

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import BusinessRuleError, NotFoundError
from src.features.competitions.formats import FORMAT_REGISTRY, get_format
from src.features.competitions.formats.base import FormatPlugin
from src.features.competitions.repository import CompetitionRepository
from src.features.competitions.schemas import (
    CompetitionDetail,
    CompetitionListResponse,
    CompetitionMatchupsResponse,
    CompetitionStandingsResponse,
    CompetitionSummary,
    FormatInfo,
    GroupStandings,
    MatchupDraft,
    MatchupEntry,
    StandingEntry,
)
from src.shared.models.competition import Competition

logger = logging.getLogger(__name__)


class CompetitionService:
    """Single entry point used by the router and by the scraping hook."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = CompetitionRepository(session)

    # ------------------------------------------------------------------
    # Format discovery
    # ------------------------------------------------------------------

    def list_formats(self) -> list[FormatInfo]:
        return [
            FormatInfo(
                format_id=p.format_id,
                display_name=p.display_name,
                n_rounds_regular=p.required_rounds_regular(),
                n_rounds_ko=p.required_rounds_ko(),
            )
            for p in FORMAT_REGISTRY.values()
        ]

    # ------------------------------------------------------------------
    # Competition lifecycle
    # ------------------------------------------------------------------

    async def list_competitions_for_season(self, season_id: int) -> CompetitionListResponse:
        rows = await self.repo.list_for_season(season_id)
        return CompetitionListResponse(
            season_id=season_id,
            competitions=[
                CompetitionSummary(
                    id=c.id,
                    season_id=c.season_id,
                    name=c.name,
                    type=c.type,
                    status=c.status,
                )
                for c in rows
            ],
        )

    async def create_playoff(
        self, season_id: int, format_id: str = "balanced_ko4"
    ) -> CompetitionDetail:
        if format_id not in FORMAT_REGISTRY:
            raise BusinessRuleError(f"Formato desconocido: {format_id}")

        existing = await self.repo.get_by_season_and_type(season_id, "playoff")
        if existing is not None:
            return self._to_detail(existing)

        plugin = get_format(format_id)
        comp = await self.repo.create(
            season_id=season_id,
            name=f"Playoff — {plugin.display_name}",
            type_="playoff",
            config={"format_id": format_id},
        )
        await self.session.commit()
        return self._to_detail(comp)

    async def start_regular_phase(
        self,
        competition_id: int,
        matchday_start: int,
        matchday_end: int,
    ) -> int:
        comp = await self._require_competition(competition_id)
        plugin = self._plugin_for(comp)

        if await self.repo.count_matchups(competition_id, phase="regular") > 0:
            # Idempotent: nothing to do.
            return 0

        n_required = plugin.required_rounds_regular()
        n_provided = matchday_end - matchday_start + 1
        if n_provided != n_required:
            raise BusinessRuleError(
                f"El formato {plugin.format_id} requiere {n_required} jornadas, "
                f"recibidas {n_provided}"
            )

        participant_ids = await self.repo.get_participant_ids(comp.season_id)
        matchday_ids = await self.repo.get_matchday_ids_in_range(
            comp.season_id, matchday_start, matchday_end
        )
        if len(matchday_ids) != n_required:
            raise BusinessRuleError(
                f"La temporada no tiene jornadas {matchday_start}..{matchday_end} "
                f"(encontradas {len(matchday_ids)} de {n_required})."
            )

        seed = random.randint(0, 2**31)
        drafts = plugin.generate_regular_phase(participant_ids, matchday_ids, seed)
        await self._persist_drafts(competition_id, drafts)

        await self.repo.update_config_patch(
            competition_id,
            {
                "seed": seed,
                "matchday_range_regular": {"start": matchday_start, "end": matchday_end},
            },
        )
        await self.repo.update_status(competition_id, "regular")
        await self.session.commit()
        return len(drafts)

    async def start_ko_phase(self, competition_id: int, ko_matchday_numbers: list[int]) -> int:
        comp = await self._require_competition(competition_id)
        plugin = self._plugin_for(comp)

        if await self.repo.count_matchups(competition_id, phase="ko") > 0:
            return 0

        n_required = plugin.required_rounds_ko()
        if len(ko_matchday_numbers) != n_required:
            raise BusinessRuleError(
                f"El formato {plugin.format_id} requiere {n_required} jornadas KO, "
                f"recibidas {len(ko_matchday_numbers)}"
            )

        unresolved = await self.repo.count_unresolved_regular(competition_id)
        if unresolved:
            raise BusinessRuleError(
                f"Quedan {unresolved} cruces de fase regular sin resolver. "
                "Termina la fase regular antes de iniciar las eliminatorias."
            )

        # Standings + snapshot for tie-breaking later.
        standings = await self._compute_standings(comp)
        flat: list[StandingEntry] = [s for g in standings for s in g.entries]

        matchday_ids = await self.repo.get_matchday_ids_by_numbers(
            comp.season_id, ko_matchday_numbers
        )
        if len(matchday_ids) != n_required:
            raise BusinessRuleError("Algunas jornadas KO solicitadas no existen en la temporada.")

        drafts = plugin.generate_ko_phase(flat, matchday_ids)
        await self._persist_drafts(competition_id, drafts)

        await self.repo.update_config_patch(
            competition_id,
            {
                "regular_standings_snapshot": [s.model_dump() for s in flat],
                "matchday_range_ko": ko_matchday_numbers,
            },
        )
        await self.repo.update_status(competition_id, "ko")
        await self.session.commit()
        return len(drafts)

    # ------------------------------------------------------------------
    # Recalculation hook — called from scraping/aggregation.py
    # ------------------------------------------------------------------

    async def recalculate_matchups_for_matchday(self, matchday_id: int) -> dict[str, int]:
        matchups = await self.repo.get_matchups_for_matchday(matchday_id)
        if not matchups:
            return {"resolved": 0, "pending": 0}

        resolved = pending = 0
        last_competition_id: int | None = None
        for m in matchups:
            last_competition_id = m.competition_id
            if m.participant_a_id is None or m.participant_b_id is None:
                pending += 1
                continue
            score_a = await self.repo.get_matchday_score(matchday_id, m.participant_a_id)
            score_b = await self.repo.get_matchday_score(matchday_id, m.participant_b_id)
            if score_a is None or score_b is None:
                pending += 1
                continue

            if score_a > score_b:
                winner = m.participant_a_id
            elif score_b > score_a:
                winner = m.participant_b_id
            else:
                if m.phase == "regular":
                    winner = None
                else:
                    comp = await self.repo.get_competition_for_matchup(m.id)
                    if comp is None:
                        pending += 1
                        continue
                    plugin = self._plugin_for(comp)
                    snapshot = [
                        StandingEntry(**s)
                        for s in (comp.config or {}).get("regular_standings_snapshot", [])
                    ]
                    winner = plugin.resolve_ko_tie(
                        m.participant_a_id, m.participant_b_id, snapshot
                    )

            await self.repo.update_matchup_result(m.id, score_a, score_b, winner)
            if winner is not None:
                await self.repo.propagate_winner_to_feeders(m.id, winner)
            resolved += 1

        await self._maybe_mark_completed(last_competition_id)
        await self.session.commit()
        return {"resolved": resolved, "pending": pending}

    async def _maybe_mark_completed(self, competition_id: int | None) -> None:
        if competition_id is None:
            return
        comp = await self.repo.get(competition_id)
        if comp is None or comp.status == "completed":
            return
        # Completed when the highest round_number matchup (final) has a winner.
        all_matchups = await self.repo.get_matchups_with_competition(competition_id)
        finals = [m for m in all_matchups if m.phase == "ko"]
        if not finals:
            return
        max_round = max(m.round_number for m in finals)
        final_round = [m for m in finals if m.round_number == max_round]
        if all(m.winner_participant_id is not None for m in final_round):
            await self.repo.update_status(competition_id, "completed")

    # ------------------------------------------------------------------
    # Read endpoints
    # ------------------------------------------------------------------

    async def get_matchups(self, competition_id: int) -> CompetitionMatchupsResponse:
        comp = await self._require_competition(competition_id)
        rows = await self.repo.list_matchups_with_names(competition_id)
        return CompetitionMatchupsResponse(
            competition=self._to_detail(comp),
            matchups=[MatchupEntry(**r) for r in rows],
        )

    async def get_standings(self, competition_id: int) -> CompetitionStandingsResponse:
        comp = await self._require_competition(competition_id)
        groups = await self._compute_standings(comp)
        return CompetitionStandingsResponse(
            competition=self._to_detail(comp),
            groups=groups,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _require_competition(self, competition_id: int) -> Competition:
        comp = await self.repo.get(competition_id)
        if comp is None:
            raise NotFoundError("Competition", competition_id)
        return comp

    def _plugin_for(self, comp: Competition) -> FormatPlugin:
        format_id = (comp.config or {}).get("format_id")
        if not format_id:
            raise BusinessRuleError(f"La competición {comp.id} no tiene format_id en su config.")
        try:
            return get_format(format_id)
        except KeyError as exc:
            raise BusinessRuleError(str(exc)) from exc

    async def _persist_drafts(self, competition_id: int, drafts: list[MatchupDraft]) -> None:
        """Persist drafts respecting feeder references.

        Drafts can carry ``feeder_a_index`` / ``feeder_b_index`` that
        reference earlier entries within the SAME draft list (not DB
        ids). We insert in order and map indices to the freshly
        assigned ``CompetitionMatchup.id`` values.
        """
        created_ids: list[int] = []
        for draft in drafts:
            feeder_a_id: int | None = None
            feeder_b_id: int | None = None
            if draft.feeder_a_index is not None:
                feeder_a_id = created_ids[draft.feeder_a_index]
            if draft.feeder_b_index is not None:
                feeder_b_id = created_ids[draft.feeder_b_index]
            row = await self.repo.insert_matchup(
                competition_id=competition_id,
                phase=draft.phase,
                group_label=draft.group_label,
                round_label=draft.round_label,
                round_number=draft.round_number,
                matchday_id=draft.matchday_id,
                participant_a_id=draft.participant_a_id,
                participant_b_id=draft.participant_b_id,
                feeder_a_id=feeder_a_id,
                feeder_b_id=feeder_b_id,
            )
            created_ids.append(row.id)

    async def _compute_standings(self, comp: Competition) -> list[GroupStandings]:
        plugin = self._plugin_for(comp)
        out: list[GroupStandings] = []
        for label in plugin.standings_groups():
            rows = await self.repo.get_standings_rows(comp.id, group_label=label)
            sorted_rows = sorted(
                rows,
                key=lambda r: (
                    -r.points,
                    -r.diff_avg,
                    -r.pts_total_vpv,
                    r.draft_order,
                ),
            )
            entries: list[StandingEntry] = []
            for idx, r in enumerate(sorted_rows, start=1):
                entries.append(
                    StandingEntry(
                        rank=idx,
                        participant_id=r.participant_id,
                        display_name=r.display_name,
                        group_label=r.group_label,
                        played=r.played,
                        wins=r.wins,
                        draws=r.draws,
                        losses=r.losses,
                        rests=r.rests,
                        points=r.points,
                        diff_avg=r.diff_avg,
                        pts_total_vpv=r.pts_total_vpv,
                    )
                )
            out.append(GroupStandings(label=label, entries=entries))
        return out

    @staticmethod
    def _to_detail(comp: Competition) -> CompetitionDetail:
        return CompetitionDetail(
            id=comp.id,
            season_id=comp.season_id,
            name=comp.name,
            type=comp.type,
            status=comp.status,
            config=comp.config,
        )
