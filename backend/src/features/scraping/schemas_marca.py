"""Pydantic schemas for the Marca-rating admin tool.

The frontend at ``/admin/marca`` lets a delegate (``Perm.MARCA``) fill
in the Marca star ratings for a single match either by uploading a
press clipping (OCR path, future) or by typing them manually.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# Valid Marca rating strings — what the ScoringEngine knows how to
# convert into points. The dropdown in the UI emits these exact values
# OR null when the player didn't play at all (no row to score).
#
# Meaning (per Marca's print edition + ScoringEngine):
#   "★"…"★★★★"  → cuantas más, mejor
#   "SC"        → "sin calificar" — jugó poco, no se puede valorar
#   "-"         → "jugó mal" — calificación negativa explícita
#   None        → "no jugó" — la fila se persiste con marca_rating NULL
#                  y pts_marca = 0
VALID_MARCA_VALUES: tuple[str, ...] = (
    "★",
    "★★",
    "★★★",
    "★★★★",
    "SC",
    "-",
)


class MarcaPlayerRow(BaseModel):
    """One eligible player for a match's marca rating."""

    player_id: int
    display_name: str
    team_id: int
    team_name: str
    # NULL = no stats row yet for this (player, matchday). The UI shows
    # an empty dropdown then; saving with `-` marks "no jugó" explicitly.
    marca_rating: str | None
    minutes_played: int
    position: str  # "POR" / "DEF" / "MED" / "DEL" / ""


class MarcaRosterResponse(BaseModel):
    """Players grouped by team for the Manual tab."""

    match_id: int
    match_label: str
    matchday_number: int
    home: list[MarcaPlayerRow]
    away: list[MarcaPlayerRow]


class MarcaAssignment(BaseModel):
    """One row of the admin's edit list.

    ``marca_rating`` is None when the admin marks the player as
    "no jugó" — the service will store NULL and pts_marca becomes 0.
    """

    player_id: int
    marca_rating: str | None = Field(default=None, max_length=10)


class MarcaApplyRequest(BaseModel):
    """Body of POST /scraping/admin/marca/apply."""

    match_id: int
    assignments: list[MarcaAssignment]
