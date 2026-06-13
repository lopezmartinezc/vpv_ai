"""Tests for the Marca-rating admin tool.

Schema-level checks here so we don't need a real DB. The end-to-end
service test will land alongside the OCR feature work.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.features.scraping.schemas_marca import (
    VALID_MARCA_VALUES,
    MarcaApplyRequest,
    MarcaAssignment,
    MarcaPlayerRow,
    MarcaRosterResponse,
)


class TestValidValuesContract:
    """The dropdown in the UI emits exactly these six strings."""

    def test_six_values(self) -> None:
        assert len(VALID_MARCA_VALUES) == 6

    def test_includes_one_to_four_stars(self) -> None:
        assert "★" in VALID_MARCA_VALUES
        assert "★★" in VALID_MARCA_VALUES
        assert "★★★" in VALID_MARCA_VALUES
        assert "★★★★" in VALID_MARCA_VALUES

    def test_includes_sc_and_dash(self) -> None:
        assert "SC" in VALID_MARCA_VALUES
        assert "-" in VALID_MARCA_VALUES


class TestMarcaAssignmentSchema:
    def test_accepts_valid_rating(self) -> None:
        a = MarcaAssignment(player_id=42, marca_rating="★★")
        assert a.player_id == 42
        assert a.marca_rating == "★★"

    def test_accepts_none_for_no_jugo(self) -> None:
        # null == "no jugó" — la fila pasa al servicio y se persiste
        # como NULL en player_stats.marca_rating.
        a = MarcaAssignment(player_id=42, marca_rating=None)
        assert a.marca_rating is None

    def test_default_is_none(self) -> None:
        a = MarcaAssignment(player_id=42)
        assert a.marca_rating is None

    def test_rejects_too_long_string(self) -> None:
        # La validez semántica (debe estar en VALID_MARCA_VALUES) la
        # comprueba el service. El schema sólo defiende la columna
        # `String(10)` para que NUNCA llegue una string desbordada.
        with pytest.raises(ValidationError):
            MarcaAssignment(player_id=42, marca_rating="x" * 11)


class TestMarcaApplyRequestShape:
    def test_groups_assignments_by_match(self) -> None:
        req = MarcaApplyRequest(
            match_id=100,
            assignments=[
                MarcaAssignment(player_id=1, marca_rating="★"),
                MarcaAssignment(player_id=2, marca_rating="-"),
                MarcaAssignment(player_id=3, marca_rating="SC"),
            ],
        )
        assert req.match_id == 100
        assert len(req.assignments) == 3

    def test_empty_assignments_is_legal(self) -> None:
        # The frontend may submit an empty list when nothing changed.
        req = MarcaApplyRequest(match_id=100, assignments=[])
        assert req.assignments == []


class TestMarcaRosterResponseShape:
    def test_round_trip(self) -> None:
        resp = MarcaRosterResponse(
            match_id=1,
            match_label="Estados Unidos vs Paraguay",
            matchday_number=2,
            home=[
                MarcaPlayerRow(
                    player_id=10,
                    display_name="Pulisic",
                    team_id=5,
                    team_name="Estados Unidos",
                    marca_rating="★★★",
                    minutes_played=90,
                    position="MED",
                )
            ],
            away=[],
        )
        assert resp.home[0].marca_rating == "★★★"
        assert resp.away == []

    def test_marca_rating_can_be_none_when_no_player_stats(self) -> None:
        # Player who didn't get a row yet because the match wasn't scraped.
        row = MarcaPlayerRow(
            player_id=10,
            display_name="X",
            team_id=5,
            team_name="Y",
            marca_rating=None,
            minutes_played=0,
            position="",
        )
        assert row.marca_rating is None
