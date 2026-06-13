"""Pydantic schemas for the Marca-rating admin tool.

The frontend at ``/admin/marca`` lets a delegate (``Perm.MARCA``) fill
in the Marca star ratings for a single match either by uploading a
press clipping (OCR path, future) or by typing them manually.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# Valid Marca rating strings — what the ScoringEngine knows how to
# convert into points. The dropdown in the UI emits these exact values.
VALID_MARCA_VALUES: tuple[str, ...] = (
    "★",  # ★
    "★★",  # ★★
    "★★★",  # ★★★
    "★★★★",  # ★★★★
    "SC",  # sin calificar
    "-",  # no jugó
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
    """One row of the admin's edit list."""

    player_id: int
    # We accept anything in VALID_MARCA_VALUES; the service validates.
    marca_rating: str = Field(..., min_length=1, max_length=10)


class MarcaApplyRequest(BaseModel):
    """Body of POST /scraping/admin/marca/apply."""

    match_id: int
    assignments: list[MarcaAssignment]
