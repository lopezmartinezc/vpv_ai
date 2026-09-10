from src.features.drafts.schemas import DraftDetailResponse, DraftParticipant, DraftPickEntry
from src.features.stats.schemas_draft import DraftValuePlayer

from ..schemas import AskRequest
from ..snapshot import Formation, RosterPlayer, Snapshot


def player(
    player_id: int = 1, priority: float | None = 100, position: str = "DEL"
) -> DraftValuePlayer:
    return DraftValuePlayer(
        player_id=player_id,
        slug=str(player_id),
        display_name=f"Jugador {player_id}",
        team_name="Equipo",
        position=position,
        photo_path=None,
        games_played=20,
        seasons_played=2,
        avg_points=5,
        total_points=100,
        ensemble_score=5,
        simple_avg=5,
        second_half_score=None,
        productivity_score=5,
        stability_score=5,
        trend_score=None,
        career_trend_pct=None,
        marca_avg=None,
        as_avg=None,
        availability=1,
        consistency=1,
        second_half_avg=None,
        goals=3,
        assists=2,
        signal="hold",
        signal_reasons=[],
        priority=priority,
        priority_base=priority,
        vorp=priority,
        participation=1,
    )


def snapshot() -> Snapshot:
    draft = DraftDetailResponse(
        id=1,
        season_id=1,
        phase="preseason",
        draft_type="snake",
        status="in_progress",
        started_at=None,
        completed_at=None,
        picks=[],
        participants=[
            DraftParticipant(
                participant_id=1, user_id=11, display_name="Private One", draft_order=1
            ),
            DraftParticipant(
                participant_id=2, user_id=22, display_name="Private Two", draft_order=2
            ),
        ],
    )
    players = [player(1, 0), player(2, -1), player(3, None), player(4, 100, "POR")]
    roster = [
        RosterPlayer(
            id=p.player_id,
            owner_id=None,
            is_available=True,
            name=p.display_name,
            position=p.position,
            team=p.team_name,
        )
        for p in players
    ]
    return Snapshot(
        draft=draft,
        players=players,
        roster=roster,
        pool_size=2,
        season_status="active",
        formations=[
            Formation(name="1-4-3-3", defenders=4, midfielders=3, forwards=3),
            Formation(name="1-3-5-2", defenders=3, midfielders=5, forwards=2),
        ],
        participation="mixto",
    )


def pick(pick_id: int = 1, number: int = 1, player_id: int = 4) -> DraftPickEntry:
    return DraftPickEntry(
        id=pick_id,
        pick_number=number,
        round_number=1,
        participant_id=1,
        display_name="Private One",
        draft_order=1,
        player_id=player_id,
        player_name=f"Jugador {player_id}",
        position="POR",
        team_name="Equipo",
    )


def request() -> AskRequest:
    return AskRequest(question="¿Qué elijo?", provider="openai", model="test-model")
