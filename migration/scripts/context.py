from dataclasses import dataclass, field


@dataclass
class MigrationContext:
    """Shared state passed between migration steps.

    Each step populates mapping dictionaries that subsequent steps consume.
    """

    # season name -> seasons.id
    season_map: dict[str, int] = field(default_factory=dict)

    # (temporada, old_slot_id) -> season_participants.id
    participant_map: dict[tuple[str, int], int] = field(default_factory=dict)

    # (temporada, team_name) -> teams.id
    team_map: dict[tuple[str, str], int] = field(default_factory=dict)

    # (temporada, jornada_num) -> matchdays.id
    matchday_map: dict[tuple[str, int], int] = field(default_factory=dict)

    # (temporada, eq_local, eq_vis) -> matches.id
    match_map: dict[tuple[str, str, str], int] = field(default_factory=dict)

    # (matchday_id, team_id) -> match_id  (reverse lookup for player_stats)
    match_team_lookup: dict[tuple[int, int], int] = field(default_factory=dict)

    # (temporada, nom_url) -> players.id
    player_map: dict[tuple[str, str], int] = field(default_factory=dict)
