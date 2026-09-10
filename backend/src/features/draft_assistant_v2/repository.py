from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal
from src.features.drafts.service import DraftService
from src.features.stats.participation import ParticipationModel
from src.features.stats.service_draft import DraftValueService
from src.shared.models.draft import Draft
from src.shared.models.player import Player
from src.shared.models.season import Season, ValidFormation
from src.shared.models.team import Team

from .errors import AssistantError
from .snapshot import Formation, RosterPlayer, Snapshot


async def read_roster(session: AsyncSession, season_id: int) -> list[RosterPlayer]:
    stmt = select(Player, Team.name).join(Team, Player.team_id == Team.id)
    rows = await session.execute(stmt.where(Player.season_id == season_id).order_by(Player.id))
    return [
        RosterPlayer(
            id=p.id,
            owner_id=p.owner_id,
            is_available=p.is_available,
            name=p.display_name,
            position=p.position,
            team=team,
        )
        for p, team in rows.tuples()
    ]


async def read_formations(session: AsyncSession) -> list[Formation]:
    rows = await session.scalars(select(ValidFormation).order_by(ValidFormation.id))
    return [
        Formation(
            name=f.formation, defenders=f.defenders, midfielders=f.midfielders, forwards=f.forwards
        )
        for f in rows
    ]


async def assemble(session: AsyncSession, draft_id: int, participation: str) -> Snapshot:
    draft = await session.get(Draft, draft_id)
    if draft is None:
        raise AssistantError("DRAFT_NOT_FOUND", "Draft no encontrado.", 404)
    season = await session.get(Season, draft.season_id)
    if season is None:
        raise AssistantError("SEASON_NOT_FOUND", "Temporada no encontrada.", 404)
    detail = await DraftService(session).get_draft_detail(draft.season_id, draft.phase)
    board = await DraftValueService(session).get_draft_values(
        draft.season_id, participation_model=ParticipationModel(participation)
    )
    return Snapshot(
        draft=detail,
        pool_size=season.draft_pool_size,
        season_status=season.status,
        players=board.players,
        roster=await read_roster(session, draft.season_id),
        formations=await read_formations(session),
        participation=participation,
    )


async def load_snapshot(draft_id: int, participation: str) -> Snapshot:
    # No legacy cache; all reads share one MVCC snapshot, closed before API waits.
    async with AsyncSessionLocal() as session, session.begin():
        await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        await session.execute(text("SET LOCAL statement_timeout = '8000ms'"))
        return await assemble(session, draft_id, participation)
