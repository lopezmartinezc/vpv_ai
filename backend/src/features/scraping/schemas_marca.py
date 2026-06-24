"""Pydantic schemas for the Marca-rating admin tool.

The frontend at ``/admin/marca`` lets a delegate (``Perm.MARCA``) fill
in the Marca star ratings for a single match either by uploading a
press clipping (OCR path, future) or by typing them manually.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# Valid Marca rating strings — what the ScoringEngine knows how to
# convert into points. The DB and API exchange these exact strings;
# the frontend's dropdown renders them as ★/★★/… visually but the
# value submitted is the numeric string.
#
# Meaning (per Marca's print edition + ScoringEngine):
#   "1"…"4"  → estrellas (cuantas más, mejor) — formato unificado
#              con Liga histórica, evita CASE Unicode en queries.
#   "SC"     → "sin calificar" — jugó poco, no se puede valorar.
#   "-"      → "jugó mal" — calificación negativa explícita.
#   None     → "no jugó" — la fila se persiste con marca_rating NULL
#               y pts_marca = 0.
VALID_MARCA_VALUES: tuple[str, ...] = (
    "1",
    "2",
    "3",
    "4",
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
    as_picas: str | None = None
    # TRUE once an admin has typed an as_picas value; the scraper will
    # not overwrite it from then on. Surfaced to the UI so the row
    # can show a small lock icon.
    as_picas_admin_set: bool = False
    minutes_played: int
    position: str  # "POR" / "DEF" / "MED" / "DEL" / ""
    # Optional alternate names / nicknames the cromo matcher should
    # consider in addition to display_name. Filled by hand on the
    # players table — the scrape never overwrites it.
    aliases: str | None = None


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


# AS picas (admin override) -------------------------------------------


# Valid AS-picas strings — what the ScoringEngine knows how to score.
# Mirrors VALID_MARCA_VALUES. "0 picas" is intentionally NOT here:
# in the AS print edition "did not earn any" is what SC means.
VALID_PICAS_VALUES: tuple[str, ...] = (
    "1",
    "2",
    "3",
    "SC",
    "-",
)


class PicasAssignment(BaseModel):
    """One row of the admin's picas-edit list."""

    player_id: int
    as_picas: str | None = Field(default=None, max_length=10)


class PicasApplyRequest(BaseModel):
    """Body of POST /scraping/admin/marca/apply-picas."""

    match_id: int
    assignments: list[PicasAssignment]


# Image preview --------------------------------------------------------


class MarcaPreviewRow(BaseModel):
    """One row extracted from the cromo image."""

    surname_clean: str
    stars: int  # 0..4
    is_substitute: bool
    minute: int | None
    raw_text: str
    confidence: float  # 0..1, Tesseract's confidence average
    # "sc" / "dash" / None — set when no stars were counted but an
    # explicit marker was detected on the right of the row.
    explicit_marker: str | None = None


class MarcaPreviewMatch(BaseModel):
    """A successful auto-match between an extracted row and a DB player."""

    row: MarcaPreviewRow
    player_id: int
    player_name: str
    # Pre-translated to one of the dropdown values so the UI can render
    # the suggestion directly. Priority: explicit_marker → stars → null.
    # - "1".."4": star count (UI renders as ★/★★/★★★/★★★★)
    # - "SC": s/c detected on the right of the row
    # - "-": dash detected on the right of the row
    # - None: nothing detected, the dropdown stays empty ("no jugó")
    marca_rating: str | None


class MarcaPreviewUnmatched(BaseModel):
    """An extracted row whose surname didn't resolve to a unique player.

    ``candidates`` is a subset of the roster the admin can pick from
    — typically the surname matched 0 players (Tesseract mangled it)
    or several (same surname on both teams).
    """

    row: MarcaPreviewRow
    candidates: list[MarcaPlayerRow]


class MarcaPreviewResponse(BaseModel):
    """Result of OCR + matching for a single match's cromo image."""

    match_id: int
    match_label: str
    matchday_number: int
    roster: list[MarcaPlayerRow]  # both teams, so the UI can fall back
    matches: list[MarcaPreviewMatch]
    unmatched: list[MarcaPreviewUnmatched]
