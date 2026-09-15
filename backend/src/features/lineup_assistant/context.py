"""What the lineup chat and the proposed eleven read, fixed by the request.

Season, matchday and asker come from the path and the JWT. The model can
influence the arguments of a tool, never these.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.lineup_assistant.optimizer import Candidate, Formation, Suggestion, best_lineup
from src.features.lineup_intel.schemas import LineupIntelResponse, SourceReading
from src.features.lineup_intel.service import LineupIntelService
from src.features.lineups.schemas import MyLineupResponse
from src.features.lineups.service import LineupService
from src.features.stats.fixtures import Fixture, FixtureStrengthService
from src.features.stats.schemas_advanced import PlayerPrediction
from src.features.stats.service_advanced import AdvancedStatsService
from src.shared.models.season import ValidFormation


@dataclass
class LineupContext:
    session: AsyncSession
    season_id: int
    matchday: int
    # Who is asking, from the JWT: "my squad" is theirs.
    user_id: int
    anonymize_participants: bool = True
    _squad: MyLineupResponse | None = field(default=None, init=False, repr=False)
    _predictions: dict[int, PlayerPrediction] | None = field(default=None, init=False, repr=False)
    _intel: LineupIntelResponse | None = field(default=None, init=False, repr=False)
    _formations: list[Formation] | None = field(default=None, init=False, repr=False)
    _fixtures: dict[str, Fixture] | None = field(default=None, init=False, repr=False)

    async def squad(self) -> MyLineupResponse:
        """The asker's squad for the matchday, as the lineup screen shows it.
        NotFoundError if they take no part in the season."""
        if self._squad is None:
            self._squad = await LineupService(self.session).get_my_lineup(
                self.user_id, self.season_id, self.matchday
            )
        return self._squad

    async def predictions(self) -> dict[int, PlayerPrediction]:
        if self._predictions is None:
            forecast = await AdvancedStatsService(self.session).get_predictions(
                self.season_id, self.matchday
            )
            self._predictions = {p.player_id: p for p in forecast.predictions}
        return self._predictions

    async def intel(self) -> LineupIntelResponse:
        if self._intel is None:
            self._intel = await LineupIntelService(self.session).read(
                self.season_id, self.matchday
            )
        return self._intel

    async def readings(self) -> dict[int, list[SourceReading]]:
        return {p.player_id: p.readings for p in (await self.intel()).players}

    async def formations(self) -> list[Formation]:
        if self._formations is None:
            rows = await self.session.execute(
                select(ValidFormation).order_by(ValidFormation.formation)
            )
            self._formations = [
                Formation(f.formation, f.defenders, f.midfielders, f.forwards)
                for f in rows.scalars()
            ]
        return self._formations

    async def fixtures(self) -> dict[str, Fixture]:
        """This matchday's fixture of each team, by team name."""
        if self._fixtures is None:
            found = await FixtureStrengthService(self.session).fixtures(
                self.season_id, from_matchday=self.matchday, count=1
            )
            self._fixtures = {f.team_name: f for f in found}
        return self._fixtures

    def participant_label(self, participant_id: int, display_name: str) -> str:
        """Other people's names are not needed for the reasoning, so by default
        they do not leave the server (ASSISTANT_ANONYMIZE_PARTICIPANTS)."""
        if not self.anonymize_participants:
            return display_name
        return f"Participante {participant_id}"

    async def p11_coverage(self) -> dict[str, set[str]]:
        """Team name → the predicted11 predictors with an eleven for it. A
        player of that team missing from one of those elevens counts 0 for it."""
        out: dict[str, set[str]] = {}
        for item in (await self.intel()).coverage:
            out.setdefault(item.team_name, set()).add(item.source)
        return out

    async def candidates(self) -> list[Candidate]:
        squad = await self.squad()
        predictions = await self.predictions()
        readings = await self.readings()
        covered = await self.p11_coverage()
        out: list[Candidate] = []
        for player in squad.squad:
            forecast = predictions.get(player.player_id)
            said = readings.get(player.player_id, [])
            probs: dict[str, int | None] = dict.fromkeys(covered.get(player.team_name, ()), 0)
            probs.update({r.source: r.probability for r in said})
            out.append(
                Candidate(
                    player_id=player.player_id,
                    name=player.display_name,
                    position=player.position,
                    team_name=player.team_name,
                    xpts_if_plays=forecast.xpts_if_plays if forecast else None,
                    has_match=player.opponent_team_name is not None,
                    spread=(forecast.xpts_ceiling - forecast.xpts) if forecast else 0.0,
                    starter_pct=forecast.starter_pct if forecast else None,
                    source_probs=probs,
                    statuses=frozenset(r.status for r in said if r.status),
                )
            )
        return out

    async def suggestion(self, formation: str | None = None) -> Suggestion | None:
        return best_lineup(await self.candidates(), await self.formations(), only=formation)
