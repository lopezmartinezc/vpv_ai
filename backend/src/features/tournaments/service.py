from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import BusinessRuleError, NotFoundError
from src.features.tournaments.schemas import (
    BracketMatch,
    BracketResponse,
    BracketRound,
    GroupResponse,
    GroupsResponse,
    PlayerOption,
    PredictionRequest,
    PredictionResponse,
    PredictionScoreBreakdown,
    PredictionsListResponse,
    PredictionsStatusResponse,
    RecalculateResponse,
    TeamGroupBatchUpdate,
    TeamGroupStanding,
    TeamOption,
)
from src.shared.models.matchday import Match, Matchday
from src.shared.models.player import Player
from src.shared.models.player_stat import PlayerStat
from src.shared.models.season import Season
from src.shared.models.team import Team
from src.shared.models.tournament_prediction import TournamentPrediction
from src.shared.models.user import User

DEFAULT_PREDICTIONS_SCORING: dict[str, int] = {
    "winner": 50,
    "dark_horse": 20,
    "top_scorer": 30,
    "best_player": 30,
    "group_first": 5,
    "group_second": 3,
    "group_third": 2,
    "group_fourth": 2,
    "group_perfect_bonus": 5,
    "best_third": 5,
    "ko_r32": 5,
    "ko_r16": 10,
    "ko_qf": 15,
    "ko_sf": 25,
    "ko_third_place": 10,
    "ko_final": 40,
}


def _ko_rule_key(pairings: list[dict[str, Any]]) -> str:
    """Infer scoring-rule key for a knockout round by its pairing count."""
    n = len(pairings)
    if n >= 16:
        return "ko_r32"
    if n == 8:
        return "ko_r16"
    if n == 4:
        return "ko_qf"
    if n == 2:
        return "ko_sf"
    if n == 1:
        code = (pairings[0].get("code") or "").upper()
        if "3" in code or "TP" in code:
            return "ko_third_place"
        return "ko_final"
    return "ko_r32"


logger = logging.getLogger(__name__)


class TournamentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    async def _get_tournament_season(self, season_id: int) -> Season:
        """Load a season and verify it's a tournament."""
        season = await self.session.get(Season, season_id)
        if season is None:
            raise NotFoundError("Season", season_id)
        if season.kind != "tournament":
            raise BusinessRuleError(
                f"La temporada {season_id} no es un torneo (kind={season.kind})"
            )
        return season

    # ------------------------------------------------------------------
    # Groups
    # ------------------------------------------------------------------

    async def get_groups(self, season_id: int) -> GroupsResponse:
        """Build the group-stage standings for a tournament."""
        season = await self._get_tournament_season(season_id)
        config = season.tournament_config or {}
        groups_cfg: dict[str, Any] = config.get("groups", {}) if isinstance(config, dict) else {}
        group_matchdays: list[int] = groups_cfg.get("matchdays", [1, 2, 3])

        # Get all teams in the season grouped by tournament_group
        teams_stmt = (
            select(Team)
            .where(Team.season_id == season_id)
            .order_by(Team.tournament_group, Team.name)
        )
        teams_result = await self.session.execute(teams_stmt)
        teams = list(teams_result.scalars().all())

        teams_by_group: dict[str, list[Team]] = defaultdict(list)
        for t in teams:
            if t.tournament_group:
                teams_by_group[t.tournament_group].append(t)

        # Get all matches in the group-stage matchdays for this season
        matches_stmt = (
            select(Match, Matchday.number.label("md_number"))
            .join(Matchday, Match.matchday_id == Matchday.id)
            .where(
                Matchday.season_id == season_id,
                Matchday.number.in_(group_matchdays),
            )
        )
        matches_result = await self.session.execute(matches_stmt)
        matches = list(matches_result.all())

        # Build standings per team
        stats: dict[int, dict[str, int]] = defaultdict(
            lambda: {"played": 0, "won": 0, "drawn": 0, "lost": 0, "gf": 0, "ga": 0}
        )

        for row in matches:
            m: Match = row[0]
            if m.home_score is None or m.away_score is None:
                continue  # not played yet
            stats[m.home_team_id]["played"] += 1
            stats[m.away_team_id]["played"] += 1
            stats[m.home_team_id]["gf"] += m.home_score
            stats[m.home_team_id]["ga"] += m.away_score
            stats[m.away_team_id]["gf"] += m.away_score
            stats[m.away_team_id]["ga"] += m.home_score
            if m.home_score > m.away_score:
                stats[m.home_team_id]["won"] += 1
                stats[m.away_team_id]["lost"] += 1
            elif m.home_score < m.away_score:
                stats[m.away_team_id]["won"] += 1
                stats[m.home_team_id]["lost"] += 1
            else:
                stats[m.home_team_id]["drawn"] += 1
                stats[m.away_team_id]["drawn"] += 1

        # Build response
        group_responses: list[GroupResponse] = []
        for group_name in sorted(teams_by_group.keys()):
            standings: list[TeamGroupStanding] = []
            for t in teams_by_group[group_name]:
                s = stats[t.id]
                pts = s["won"] * 3 + s["drawn"]
                standings.append(
                    TeamGroupStanding(
                        team_id=t.id,
                        team_name=t.name,
                        short_name=t.short_name,
                        logo_path=t.logo_path,
                        played=s["played"],
                        won=s["won"],
                        drawn=s["drawn"],
                        lost=s["lost"],
                        goals_for=s["gf"],
                        goals_against=s["ga"],
                        goal_diff=s["gf"] - s["ga"],
                        points=pts,
                    )
                )
            # Sort by points desc, then goal_diff desc, then gf desc
            standings.sort(key=lambda x: (-x.points, -x.goal_diff, -x.goals_for, x.team_name))
            group_responses.append(GroupResponse(name=group_name, teams=standings))

        return GroupsResponse(
            season_id=season_id,
            season_name=season.name,
            tournament_type=season.tournament_type,
            groups=group_responses,
        )

    # ------------------------------------------------------------------
    # Bracket
    # ------------------------------------------------------------------

    async def get_bracket(self, season_id: int) -> BracketResponse:
        """Build the knockout bracket from tournament_config + matches.

        Where the official match row for a knockout slot doesn't yet
        exist, we resolve its placeholders (``1A``, ``2C``, ``3:ABC...``,
        ``W12``, ``L12``) against the CURRENT group standings and any
        knockout matches already played. The resulting team goes into
        ``home_provisional_*``/``away_provisional_*`` so the frontend
        can render it in italics — official teams keep using the
        ``home_team_id``/``away_team_id`` channel.
        """
        season = await self._get_tournament_season(season_id)
        config = season.tournament_config or {}
        knockout: dict[str, Any] = config.get("knockout", {}) if isinstance(config, dict) else {}
        rounds_cfg: list[dict[str, Any]] = knockout.get("rounds", [])

        if not rounds_cfg:
            return BracketResponse(
                season_id=season_id,
                season_name=season.name,
                rounds=[],
            )

        # Preload teams for name/logo lookup
        teams_stmt = select(Team).where(Team.season_id == season_id)
        teams_result = await self.session.execute(teams_stmt)
        teams_by_id = {t.id: t for t in teams_result.scalars().all()}

        # Build current group standings so we can resolve "1A", "2C",
        # "3:ABCEFI..." placeholders.
        groups_resp = await self.get_groups(season_id)
        group_standings: dict[str, list[TeamGroupStanding]] = {
            g.name: g.teams for g in groups_resp.groups
        }
        third_place_assignments = self._compute_best_third_assignments(group_standings)

        # Build match_code -> winner/loser team id for any KO match
        # already played (W12, L12 placeholders).
        winner_by_code, loser_by_code = await self._compute_knockout_outcomes(
            season_id,
            rounds_cfg,
            teams_by_id,
            group_standings=group_standings,
            third_place_assignments=third_place_assignments,
        )

        bracket_rounds: list[BracketRound] = []
        for round_cfg in rounds_cfg:
            md_number = int(round_cfg.get("matchday", 0))
            round_name = str(round_cfg.get("name", f"Ronda J{md_number}"))
            pairings: list[dict[str, Any]] = round_cfg.get("pairings", []) or []

            matches_stmt = (
                select(Match)
                .join(Matchday, Match.matchday_id == Matchday.id)
                .where(
                    Matchday.season_id == season_id,
                    Matchday.number == md_number,
                )
                .order_by(Match.played_at.asc().nulls_last(), Match.id)
            )
            matches_result = await self.session.execute(matches_stmt)
            matches = list(matches_result.scalars().all())

            bm_list: list[BracketMatch] = []

            if matches:
                # Real matches exist. Attach each to its config pairing by
                # the TEAMS involved, not by list position: the DB orders
                # matches chronologically (played_at) while pairings follow
                # bracket order (M73, M74, …), so an index match would wire
                # e.g. M74's real fixture into M75's bracket slot and scramble
                # the whole tree. Fall back to index only when a match's teams
                # don't resolve to any pairing.
                pairing_by_teamset: dict[frozenset[int], dict[str, Any]] = {}
                for pairing in pairings:
                    ts = self._pairing_expected_team_ids(
                        pairing,
                        group_standings=group_standings,
                        third_place_assignments=third_place_assignments,
                        winner_by_code=winner_by_code,
                        loser_by_code=loser_by_code,
                        teams_by_id=teams_by_id,
                    )
                    if ts is not None:
                        pairing_by_teamset[ts] = pairing

                for idx, m in enumerate(matches):
                    home = teams_by_id.get(m.home_team_id)
                    away = teams_by_id.get(m.away_team_id)
                    played = m.home_score is not None and m.away_score is not None
                    pairing = pairing_by_teamset.get(
                        frozenset({m.home_team_id, m.away_team_id})
                    )
                    if pairing is None:
                        pairing = pairings[idx] if idx < len(pairings) else {}
                    bm_list.append(
                        BracketMatch(
                            match_id=m.id,
                            home_team_id=m.home_team_id,
                            home_team_name=home.name if home else None,
                            home_logo=home.logo_path if home else None,
                            home_score=m.home_score,
                            away_team_id=m.away_team_id,
                            away_team_name=away.name if away else None,
                            away_logo=away.logo_path if away else None,
                            away_score=m.away_score,
                            played=played,
                            match_code=pairing.get("code"),
                            home_placeholder=pairing.get("home"),
                            away_placeholder=pairing.get("away"),
                            label=pairing.get("label"),
                        )
                    )
            else:
                # No matches yet: render placeholders from tournament_config
                # pairings and try to resolve each one against current group
                # standings or already-played knockout matches.
                for pairing in pairings:
                    home_ph = pairing.get("home")
                    away_ph = pairing.get("away")
                    home_team = self._resolve_placeholder(
                        home_ph,
                        group_standings=group_standings,
                        third_place_assignments=third_place_assignments,
                        winner_by_code=winner_by_code,
                        loser_by_code=loser_by_code,
                        teams_by_id=teams_by_id,
                        match_code=pairing.get("code"),
                    )
                    away_team = self._resolve_placeholder(
                        away_ph,
                        group_standings=group_standings,
                        third_place_assignments=third_place_assignments,
                        winner_by_code=winner_by_code,
                        loser_by_code=loser_by_code,
                        teams_by_id=teams_by_id,
                        match_code=pairing.get("code"),
                    )
                    bm_list.append(
                        BracketMatch(
                            match_id=None,
                            home_team_id=None,
                            home_team_name=None,
                            home_logo=None,
                            home_score=None,
                            away_team_id=None,
                            away_team_name=None,
                            away_logo=None,
                            away_score=None,
                            played=False,
                            match_code=pairing.get("code"),
                            home_placeholder=home_ph,
                            away_placeholder=away_ph,
                            label=pairing.get("label"),
                            home_provisional_team_id=home_team.id if home_team else None,
                            home_provisional_team_name=home_team.name if home_team else None,
                            home_provisional_logo=home_team.logo_path if home_team else None,
                            away_provisional_team_id=away_team.id if away_team else None,
                            away_provisional_team_name=away_team.name if away_team else None,
                            away_provisional_logo=away_team.logo_path if away_team else None,
                        )
                    )
            bracket_rounds.append(
                BracketRound(name=round_name, matchday=md_number, matches=bm_list)
            )

        return BracketResponse(
            season_id=season_id,
            season_name=season.name,
            rounds=bracket_rounds,
        )

    def _compute_best_third_assignments(
        self, group_standings: dict[str, list[TeamGroupStanding]]
    ) -> dict[str, str]:
        """For Mundial-style brackets, decide which 8 of the 12 third-placed
        teams advance and return a ``match_code -> "3X"`` mapping.

        Uses ``resolve_third_place_assignments`` (Annexe C) on whatever
        third-placed group letters look best by current points / GD / GF.
        Returns ``{}`` if no 8-letter combination resolves (not enough
        groups finished, lookup miss, etc.).
        """
        from src.features.tournaments.data.third_place_lookup import (
            resolve_third_place_assignments,
        )

        if len(group_standings) < 8:
            return {}

        # Pick the 8 best 3rd-placed teams across all groups.
        thirds: list[tuple[str, TeamGroupStanding]] = []
        for group_name, teams in group_standings.items():
            if len(teams) < 3:
                continue
            thirds.append((group_name, teams[2]))
        if len(thirds) < 8:
            return {}
        thirds.sort(
            key=lambda gt: (-gt[1].points, -gt[1].goal_diff, -gt[1].goals_for, gt[1].team_name)
        )
        qualifying = {g for g, _ in thirds[:8]}
        return resolve_third_place_assignments(qualifying) or {}

    def _pairing_expected_team_ids(
        self,
        pairing: dict[str, Any],
        *,
        group_standings: dict[str, list[TeamGroupStanding]],
        third_place_assignments: dict[str, str],
        winner_by_code: dict[str, int],
        loser_by_code: dict[str, int],
        teams_by_id: dict[int, Team],
    ) -> frozenset[int] | None:
        """The set of the two team ids a pairing currently resolves to.

        Resolves both placeholders (``1A`` / ``2C`` / ``3:…`` / ``Wxx`` /
        ``Lxx``) against the standings and known KO outcomes. Returns a
        2-element frozenset, or ``None`` if either side can't be resolved
        yet — used to attach real ``matches`` rows to their bracket slot by
        identity instead of by chronological position.
        """
        home = self._resolve_placeholder(
            pairing.get("home"),
            group_standings=group_standings,
            third_place_assignments=third_place_assignments,
            winner_by_code=winner_by_code,
            loser_by_code=loser_by_code,
            teams_by_id=teams_by_id,
            match_code=pairing.get("code"),
        )
        away = self._resolve_placeholder(
            pairing.get("away"),
            group_standings=group_standings,
            third_place_assignments=third_place_assignments,
            winner_by_code=winner_by_code,
            loser_by_code=loser_by_code,
            teams_by_id=teams_by_id,
            match_code=pairing.get("code"),
        )
        if home is None or away is None or home.id == away.id:
            return None
        return frozenset({home.id, away.id})

    async def _compute_knockout_outcomes(
        self,
        season_id: int,
        rounds_cfg: list[dict[str, Any]],
        teams_by_id: dict[int, Team],
        *,
        group_standings: dict[str, list[TeamGroupStanding]],
        third_place_assignments: dict[str, str],
    ) -> tuple[dict[str, int], dict[str, int]]:
        """Resolve W12/L12 placeholders from already-played KO matches.

        Walks the rounds in config order (so each round's W/L outcomes are
        available when resolving the next), attaches every played ``matches``
        row to its pairing by the TEAMS involved — never by list position,
        since the DB orders matches chronologically while pairings follow
        bracket order — and records winner / loser team_ids keyed by the
        pairing's match_code.
        """
        winners: dict[str, int] = {}
        losers: dict[str, int] = {}
        for round_cfg in rounds_cfg:
            md_number = int(round_cfg.get("matchday", 0))
            pairings = round_cfg.get("pairings", []) or []
            if not pairings:
                continue
            matches_stmt = (
                select(Match)
                .join(Matchday, Match.matchday_id == Matchday.id)
                .where(
                    Matchday.season_id == season_id,
                    Matchday.number == md_number,
                )
                .order_by(Match.played_at.asc().nulls_last(), Match.id)
            )
            res = await self.session.execute(matches_stmt)
            matches = list(res.scalars().all())

            # Expected team-set -> match_code for this round, using outcomes
            # resolved so far (earlier rounds already populated winners/losers).
            code_by_teamset: dict[frozenset[int], str] = {}
            for pairing in pairings:
                code = pairing.get("code")
                if not code:
                    continue
                ts = self._pairing_expected_team_ids(
                    pairing,
                    group_standings=group_standings,
                    third_place_assignments=third_place_assignments,
                    winner_by_code=winners,
                    loser_by_code=losers,
                    teams_by_id=teams_by_id,
                )
                if ts is not None:
                    code_by_teamset[ts] = code

            for idx, m in enumerate(matches):
                if m.home_score is None or m.away_score is None:
                    continue
                if m.home_team_id not in teams_by_id or m.away_team_id not in teams_by_id:
                    continue
                code = code_by_teamset.get(frozenset({m.home_team_id, m.away_team_id}))
                if code is None:
                    # Fallback: positional pairing when teams don't resolve.
                    code = pairings[idx].get("code") if idx < len(pairings) else None
                if not code:
                    continue
                # Penalty-shootout override: a KO tie decided on penalties is
                # level on the pitch, so the admin records who advanced in
                # ko_winner_team_id. It wins regardless of the score.
                ko_winner = getattr(m, "ko_winner_team_id", None)
                if ko_winner in (m.home_team_id, m.away_team_id):
                    winners[code] = ko_winner
                    losers[code] = (
                        m.away_team_id if ko_winner == m.home_team_id else m.home_team_id
                    )
                elif m.home_score > m.away_score:
                    winners[code] = m.home_team_id
                    losers[code] = m.away_team_id
                elif m.away_score > m.home_score:
                    winners[code] = m.away_team_id
                    losers[code] = m.home_team_id
                # Ties with no recorded penalty winner: don't propagate yet.
        return winners, losers

    def _resolve_placeholder(
        self,
        placeholder: str | None,
        *,
        group_standings: dict[str, list[TeamGroupStanding]],
        third_place_assignments: dict[str, str],
        winner_by_code: dict[str, int],
        loser_by_code: dict[str, int],
        teams_by_id: dict[int, Team],
        match_code: str | None,
    ) -> Team | None:
        """Translate a placeholder like '1A' / '2C' / '3:ABCEFI' / 'W12'
        into the concrete Team it provisionally represents, using current
        standings and any KO outcomes already known.

        Returns None when the placeholder can't be resolved yet (group
        stage hasn't decided, best-thirds table has no match for the
        current standings, parent match still pending, …).
        """
        if not placeholder:
            return None
        p = placeholder.strip()

        # "1A", "2A": positional within a group
        if len(p) == 2 and p[0] in "1234" and p[1].isalpha():
            pos = int(p[0]) - 1
            group_name = p[1].upper()
            teams = group_standings.get(group_name) or []
            if pos < len(teams) and teams[pos].played > 0:
                return teams_by_id.get(teams[pos].team_id)
            return None

        # "3:ABCEFI..." — best third destined for THIS match_code
        if p.startswith("3:"):
            assigned = third_place_assignments.get(match_code or "")
            if not assigned or len(assigned) != 2 or assigned[0] != "3":
                return None
            group_name = assigned[1].upper()
            teams = group_standings.get(group_name) or []
            if len(teams) >= 3 and teams[2].played > 0:
                return teams_by_id.get(teams[2].team_id)
            return None

        # "Wxx" / "Lxx" — winner / loser of an earlier KO match
        if p.startswith("W") or p.startswith("L"):
            code = f"M{p[1:]}"
            team_id = (winner_by_code if p.startswith("W") else loser_by_code).get(code)
            if team_id is None:
                return None
            return teams_by_id.get(team_id)

        return None

    # ------------------------------------------------------------------
    # Predictions
    # ------------------------------------------------------------------

    async def _decorate_prediction(
        self, pred: TournamentPrediction, include_user_name: bool = True
    ) -> PredictionResponse:
        """Build a PredictionResponse with denormalized names."""
        winner_name = None
        if pred.winner_team_id is not None:
            t = await self.session.get(Team, pred.winner_team_id)
            winner_name = t.name if t else None
        top_scorer_name = None
        if pred.top_scorer_player_id is not None:
            p = await self.session.get(Player, pred.top_scorer_player_id)
            top_scorer_name = p.display_name if p else None
        best_player_name = None
        if pred.best_player_id is not None:
            p = await self.session.get(Player, pred.best_player_id)
            best_player_name = p.display_name if p else None
        dark_horse_name = None
        if pred.dark_horse_team_id is not None:
            t = await self.session.get(Team, pred.dark_horse_team_id)
            dark_horse_name = t.name if t else None
        display_name = None
        if include_user_name:
            u = await self.session.get(User, pred.user_id)
            display_name = u.display_name if u else None

        return PredictionResponse(
            id=pred.id,
            season_id=pred.season_id,
            user_id=pred.user_id,
            display_name=display_name,
            winner_team_id=pred.winner_team_id,
            winner_team_name=winner_name,
            top_scorer_player_id=pred.top_scorer_player_id,
            top_scorer_player_name=top_scorer_name,
            best_player_id=pred.best_player_id,
            best_player_name=best_player_name,
            dark_horse_team_id=pred.dark_horse_team_id,
            dark_horse_team_name=dark_horse_name,
            notes=pred.notes,
            bonus_points=pred.bonus_points,
            bracket_predictions=pred.bracket_predictions,
        )

    async def get_my_prediction(self, season_id: int, user_id: int) -> PredictionResponse | None:
        await self._get_tournament_season(season_id)
        stmt = select(TournamentPrediction).where(
            TournamentPrediction.season_id == season_id,
            TournamentPrediction.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        pred = result.scalar_one_or_none()
        if pred is None:
            return None
        return await self._decorate_prediction(pred, include_user_name=False)

    async def get_predictions_deadline(self, season_id: int) -> datetime | None:
        """Compute the deadline for predictions: first_match_at of matchday 1
        minus `lineup_deadline_min` (reuses the league deadline config).
        Returns None when no first match is scheduled yet (predictions stay open).
        """
        from datetime import timedelta

        season = await self.session.get(Season, season_id)
        if season is None:
            return None
        stmt = (
            select(Matchday.first_match_at)
            .where(Matchday.season_id == season_id)
            .order_by(Matchday.number.asc())
            .limit(1)
        )
        first_match = (await self.session.execute(stmt)).scalar_one_or_none()
        if first_match is None:
            return None
        return first_match - timedelta(minutes=season.lineup_deadline_min or 0)

    async def _are_predictions_locked(self, season_id: int) -> tuple[bool, datetime | None]:
        from datetime import UTC, datetime

        deadline = await self.get_predictions_deadline(season_id)
        if deadline is None:
            return False, None
        return datetime.now(UTC) >= deadline, deadline

    async def get_predictions_status(self, season_id: int) -> PredictionsStatusResponse:
        await self._get_tournament_season(season_id)
        locked, deadline = await self._are_predictions_locked(season_id)

        stmt = (
            select(Matchday.first_match_at)
            .where(Matchday.season_id == season_id)
            .order_by(Matchday.number.asc())
            .limit(1)
        )
        first_match = (await self.session.execute(stmt)).scalar_one_or_none()

        return PredictionsStatusResponse(
            season_id=season_id,
            locked=locked,
            deadline_at=deadline.isoformat() if deadline else None,
            first_match_at=first_match.isoformat() if first_match else None,
        )

    async def upsert_my_prediction(
        self, season_id: int, user_id: int, body: PredictionRequest
    ) -> PredictionResponse:
        await self._get_tournament_season(season_id)
        from datetime import UTC, datetime

        locked, deadline = await self._are_predictions_locked(season_id)
        if locked:
            raise BusinessRuleError(
                f"Las predicciones se cerraron el {deadline.isoformat() if deadline else 'inicio del torneo'} — ya no se pueden editar."
            )

        stmt = select(TournamentPrediction).where(
            TournamentPrediction.season_id == season_id,
            TournamentPrediction.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        pred = result.scalar_one_or_none()

        if pred is None:
            pred = TournamentPrediction(
                season_id=season_id,
                user_id=user_id,
                winner_team_id=body.winner_team_id,
                top_scorer_player_id=body.top_scorer_player_id,
                best_player_id=body.best_player_id,
                dark_horse_team_id=body.dark_horse_team_id,
                notes=body.notes,
                bracket_predictions=body.bracket_predictions,
            )
            self.session.add(pred)
        else:
            pred.winner_team_id = body.winner_team_id
            pred.top_scorer_player_id = body.top_scorer_player_id
            pred.best_player_id = body.best_player_id
            pred.dark_horse_team_id = body.dark_horse_team_id
            pred.notes = body.notes
            if body.bracket_predictions is not None:
                pred.bracket_predictions = body.bracket_predictions
            # updated_at column is naive in DB; strip tz from UTC datetime
            pred.updated_at = datetime.now(UTC).replace(tzinfo=None)

        await self.session.commit()
        await self.session.refresh(pred)
        return await self._decorate_prediction(pred, include_user_name=False)

    async def list_predictions(self, season_id: int) -> PredictionsListResponse:
        """Return all participants' predictions (visible after submission)."""
        season = await self._get_tournament_season(season_id)
        stmt = select(TournamentPrediction).where(TournamentPrediction.season_id == season_id)
        result = await self.session.execute(stmt)
        preds = list(result.scalars().all())

        decorated = [await self._decorate_prediction(p) for p in preds]
        decorated.sort(key=lambda p: (-p.bonus_points, (p.display_name or "").lower()))
        return PredictionsListResponse(
            season_id=season_id,
            season_name=season.name,
            predictions=decorated,
        )

    # ------------------------------------------------------------------
    # Helper endpoints for predictions UI
    # ------------------------------------------------------------------

    async def list_teams(self, season_id: int) -> list[TeamOption]:
        await self._get_tournament_season(season_id)
        stmt = (
            select(Team)
            .where(Team.season_id == season_id)
            .order_by(Team.tournament_group, Team.name)
        )
        result = await self.session.execute(stmt)
        return [
            TeamOption(
                id=t.id,
                name=t.name,
                short_name=t.short_name,
                logo_path=t.logo_path,
                tournament_group=t.tournament_group,
            )
            for t in result.scalars().all()
        ]

    async def assign_team_groups(
        self,
        season_id: int,
        body: TeamGroupBatchUpdate,
    ) -> list[TeamOption]:
        """Batch-assign teams to tournament groups (admin)."""
        await self._get_tournament_season(season_id)

        # Build a map team_id -> group_name from the request
        wanted: dict[int, str | None] = {a.team_id: a.group_name for a in body.assignments}
        if not wanted:
            return await self.list_teams(season_id)

        # Load all referenced teams in one query and check they belong to the season
        stmt = select(Team).where(Team.id.in_(list(wanted.keys())))
        result = await self.session.execute(stmt)
        teams = list(result.scalars().all())
        for t in teams:
            if t.season_id != season_id:
                raise BusinessRuleError(
                    f"El equipo {t.id} no pertenece a la temporada {season_id}"
                )
            new_group = wanted[t.id]
            # Normalize empty string to None
            t.tournament_group = (new_group or "").strip().upper() or None

        await self.session.commit()
        return await self.list_teams(season_id)

    # ------------------------------------------------------------------
    # Auto-scoring
    # ------------------------------------------------------------------

    def _scoring_rules(self, season: Season) -> dict[str, int]:
        cfg = season.tournament_config or {}
        raw = cfg.get("predictions_scoring") if isinstance(cfg, dict) else None
        merged = dict(DEFAULT_PREDICTIONS_SCORING)
        if isinstance(raw, dict):
            for k, v in raw.items():
                if isinstance(v, int):
                    merged[k] = v
        return merged

    async def _actual_group_order(self, season_id: int) -> dict[str, list[int]]:
        """Real ranking 1º-4º per group, derived from played matches."""
        groups = await self.get_groups(season_id)
        return {g.name: [t.team_id for t in g.teams] for g in groups.groups}

    async def _actual_best_thirds(self, season_id: int) -> list[str]:
        """Letters of groups whose 3rd-placed team qualified as a best third.

        Picks the top-8 thirds across all groups, ranked by points → goal diff →
        goals_for. Returns an empty list when not enough thirds are available.
        """
        groups = await self.get_groups(season_id)
        thirds: list[tuple[int, int, int, str]] = []  # (-pts, -gd, -gf, group)
        for g in groups.groups:
            if len(g.teams) >= 3:
                t = g.teams[2]
                thirds.append((-t.points, -t.goal_diff, -t.goals_for, g.name))
        if len(thirds) < 8:
            return []
        thirds.sort()
        return sorted(grp for _, _, _, grp in thirds[:8])

    async def _actual_match_winners(self, season: Season) -> tuple[dict[str, int], dict[str, str]]:
        """For each knockout match_code, compute the winner team_id.

        Returns (winners_by_code, rule_key_by_code).
        """
        cfg = season.tournament_config or {}
        knockout = cfg.get("knockout", {}) if isinstance(cfg, dict) else {}
        rounds_cfg: list[dict[str, Any]] = knockout.get("rounds", []) or []

        winners: dict[str, int] = {}
        rule_keys: dict[str, str] = {}

        for round_cfg in rounds_cfg:
            md_number = int(round_cfg.get("matchday", 0))
            pairings: list[dict[str, Any]] = round_cfg.get("pairings", []) or []
            rule_key = _ko_rule_key(pairings)

            matches_stmt = (
                select(Match)
                .join(Matchday, Match.matchday_id == Matchday.id)
                .where(
                    Matchday.season_id == season.id,
                    Matchday.number == md_number,
                )
                .order_by(Match.played_at.asc().nulls_last(), Match.id)
            )
            result = await self.session.execute(matches_stmt)
            matches = list(result.scalars().all())
            for idx, m in enumerate(matches):
                if m.home_score is None or m.away_score is None:
                    continue
                pairing = pairings[idx] if idx < len(pairings) else {}
                code = pairing.get("code")
                if not code:
                    continue
                if m.home_score > m.away_score:
                    winners[code] = m.home_team_id
                elif m.away_score > m.home_score:
                    winners[code] = m.away_team_id
                # Draws (penalty shootouts) are not tracked here; require manual override
                rule_keys[code] = rule_key
        return winners, rule_keys

    async def _actual_top_scorer(self, season_id: int) -> int | None:
        stmt = (
            select(PlayerStat.player_id, func.sum(PlayerStat.goals).label("g"))
            .join(Matchday, PlayerStat.matchday_id == Matchday.id)
            .where(Matchday.season_id == season_id)
            .group_by(PlayerStat.player_id)
            .order_by(func.sum(PlayerStat.goals).desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        row = result.first()
        if row is None or not row.g:
            return None
        return int(row.player_id)

    async def _actual_best_player(self, season_id: int) -> int | None:
        stmt = (
            select(PlayerStat.player_id, func.sum(PlayerStat.pts_total).label("p"))
            .join(Matchday, PlayerStat.matchday_id == Matchday.id)
            .where(Matchday.season_id == season_id)
            .group_by(PlayerStat.player_id)
            .order_by(func.sum(PlayerStat.pts_total).desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        row = result.first()
        if row is None or not row.p:
            return None
        return int(row.player_id)

    async def _actual_winner_team(self, season: Season) -> int | None:
        """Winner of the tournament: winner of the round with a single non-third-place match."""
        cfg = season.tournament_config or {}
        knockout = cfg.get("knockout", {}) if isinstance(cfg, dict) else {}
        rounds_cfg: list[dict[str, Any]] = knockout.get("rounds", []) or []
        for round_cfg in rounds_cfg:
            pairings = round_cfg.get("pairings", []) or []
            if _ko_rule_key(pairings) != "ko_final":
                continue
            md_number = int(round_cfg.get("matchday", 0))
            stmt = (
                select(Match)
                .join(Matchday, Match.matchday_id == Matchday.id)
                .where(Matchday.season_id == season.id, Matchday.number == md_number)
            )
            result = await self.session.execute(stmt)
            matches = list(result.scalars().all())
            for m in matches:
                if m.home_score is None or m.away_score is None:
                    continue
                if m.home_score > m.away_score:
                    return m.home_team_id
                if m.away_score > m.home_score:
                    return m.away_team_id
        return None

    async def _compute_actuals(self, season: Season) -> dict[str, Any]:
        winners_by_code, rule_keys_by_code = await self._actual_match_winners(season)
        # Semifinalists = winners of QF matches (those who reached SF)
        semifinalists = {
            tid for code, tid in winners_by_code.items() if rule_keys_by_code.get(code) == "ko_qf"
        }
        return {
            "winner_team_id": await self._actual_winner_team(season),
            "top_scorer_player_id": await self._actual_top_scorer(season.id),
            "best_player_id": await self._actual_best_player(season.id),
            "groups_order": await self._actual_group_order(season.id),
            "best_thirds": await self._actual_best_thirds(season.id),
            "match_winners": winners_by_code,
            "match_rule_keys": rule_keys_by_code,
            "semifinalists": list(semifinalists),
        }

    def _score_one(
        self,
        pred: TournamentPrediction,
        actuals: dict[str, Any],
        rules: dict[str, int],
    ) -> tuple[int, dict[str, int]]:
        detail: dict[str, int] = {}
        total = 0

        if actuals["winner_team_id"] and pred.winner_team_id == actuals["winner_team_id"]:
            detail["winner"] = rules["winner"]
            total += rules["winner"]

        # Dark horse: acierto si el equipo sorpresa llegó a semifinales
        # (ganó su cuartos de final) y no es el campeón.
        semifinalists = set(actuals.get("semifinalists") or [])
        if (
            pred.dark_horse_team_id
            and pred.dark_horse_team_id in semifinalists
            and pred.dark_horse_team_id != actuals.get("winner_team_id")
        ):
            detail["dark_horse"] = rules["dark_horse"]
            total += rules["dark_horse"]

        if (
            actuals["top_scorer_player_id"]
            and pred.top_scorer_player_id == actuals["top_scorer_player_id"]
        ):
            detail["top_scorer"] = rules["top_scorer"]
            total += rules["top_scorer"]

        if actuals["best_player_id"] and pred.best_player_id == actuals["best_player_id"]:
            detail["best_player"] = rules["best_player"]
            total += rules["best_player"]

        bracket = pred.bracket_predictions or {}
        pred_groups: dict[str, list[int]] = bracket.get("groups") or {}
        actual_groups: dict[str, list[int]] = actuals.get("groups_order") or {}

        group_keys = ("group_first", "group_second", "group_third", "group_fourth")
        for group_name, predicted_order in pred_groups.items():
            actual_order = actual_groups.get(group_name) or []
            if not actual_order:
                continue
            position_hits = 0
            for idx in range(min(len(predicted_order), len(actual_order), 4)):
                if predicted_order[idx] and predicted_order[idx] == actual_order[idx]:
                    detail[group_keys[idx]] = (
                        detail.get(group_keys[idx], 0) + rules[group_keys[idx]]
                    )
                    total += rules[group_keys[idx]]
                    position_hits += 1
            if position_hits == 4 and rules["group_perfect_bonus"]:
                detail["group_perfect_bonus"] = (
                    detail.get("group_perfect_bonus", 0) + rules["group_perfect_bonus"]
                )
                total += rules["group_perfect_bonus"]

        pred_thirds = set(bracket.get("best_thirds") or [])
        actual_thirds = set(actuals.get("best_thirds") or [])
        if pred_thirds and actual_thirds:
            hits = len(pred_thirds & actual_thirds)
            if hits:
                detail["best_third"] = hits * rules["best_third"]
                total += hits * rules["best_third"]

        pred_winners: dict[str, int] = bracket.get("match_winners") or {}
        actual_winners: dict[str, int] = actuals.get("match_winners") or {}
        rule_keys_by_code: dict[str, str] = actuals.get("match_rule_keys") or {}
        for code, team_id in pred_winners.items():
            if not team_id:
                continue
            if actual_winners.get(code) == team_id:
                key = rule_keys_by_code.get(code, "ko_r32")
                detail[key] = detail.get(key, 0) + rules[key]
                total += rules[key]

        return total, detail

    async def recalculate_predictions(self, season_id: int) -> RecalculateResponse:
        season = await self._get_tournament_season(season_id)
        rules = self._scoring_rules(season)
        actuals = await self._compute_actuals(season)

        stmt = select(TournamentPrediction).where(TournamentPrediction.season_id == season_id)
        result = await self.session.execute(stmt)
        preds = list(result.scalars().all())

        breakdowns: list[PredictionScoreBreakdown] = []
        for p in preds:
            total, detail = self._score_one(p, actuals, rules)
            p.bonus_points = total
            user = await self.session.get(User, p.user_id)
            breakdowns.append(
                PredictionScoreBreakdown(
                    user_id=p.user_id,
                    display_name=user.display_name if user else None,
                    total=total,
                    detail=detail,
                )
            )

        await self.session.commit()
        breakdowns.sort(key=lambda b: (-b.total, (b.display_name or "").lower()))

        actuals_summary: dict[str, Any] = {
            k: v
            for k, v in actuals.items()
            if k
            not in (
                "groups_order",
                "match_winners",
                "match_rule_keys",
                "semifinalists",
            )
        }
        return RecalculateResponse(
            season_id=season_id,
            scoring_rules=rules,
            actuals=actuals_summary,
            results=breakdowns,
        )

    async def list_players(self, season_id: int) -> list[PlayerOption]:
        await self._get_tournament_season(season_id)
        stmt = (
            select(
                Player.id,
                Player.display_name,
                Player.position,
                Player.photo_path,
                Team.id.label("team_id"),
                Team.name.label("team_name"),
            )
            .join(Team, Player.team_id == Team.id)
            .where(
                Player.season_id == season_id,
                # Hide players sync-rosters has flagged as off-squad so they
                # don't appear in the predicciones combobox.
                Player.is_available.is_(True),
            )
            .order_by(Team.name, Player.display_name)
        )
        result = await self.session.execute(stmt)
        return [
            PlayerOption(
                id=row.id,
                name=row.display_name,
                team_id=row.team_id,
                team_name=row.team_name,
                position=row.position or None,
                photo_path=row.photo_path,
            )
            for row in result.all()
        ]
