from __future__ import annotations

from enum import IntFlag


class Perm(IntFlag):
    """Bitmap permissions for delegated admin tasks.

    Each bit represents a group of endpoints that can be granted independently.
    Admin (is_admin=True) bypasses all permission checks.
    """

    SCRAPING = 1
    STATS = 2
    ACHIEVEMENTS = 4
    DRAFT = 8
    ECONOMY = 16
    TELEGRAM = 32
    MATCHDAYS = 64
    PLAYERS = 128
    LINEUPS_ADMIN = 256
    PARTICIPANTS = 512
    # Notas Marca por partido. Delegable sin tener que dar SCRAPING
    # o STATS — el rol Marca solo escribe player_stats.marca_rating
    # y dispara el re-aggregate de la jornada.
    MARCA = 1024


# Labels for UI display (Spanish)
PERM_LABELS: dict[Perm, str] = {
    Perm.SCRAPING: "Scraping",
    Perm.STATS: "Estadisticas",
    Perm.ACHIEVEMENTS: "Logros",
    Perm.DRAFT: "Draft",
    Perm.ECONOMY: "Economia",
    Perm.TELEGRAM: "Telegram",
    Perm.MATCHDAYS: "Jornadas",
    Perm.PLAYERS: "Jugadores",
    Perm.LINEUPS_ADMIN: "Alineaciones admin",
    Perm.PARTICIPANTS: "Participantes",
    Perm.MARCA: "Notas Marca",
}
