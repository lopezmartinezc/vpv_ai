"""Unit tests for the OpenCV-based Marca cromo parser.

The CV helpers (`_count_stars`, `_has_dash`, `_is_sub_arrow`,
`_find_column_split`, `_find_table_region`) are exercised on tiny
synthetic numpy images so CI doesn't need Tesseract.

`_detect_row_centers` and `parse_marca_image` are tested with
`_ocr_column_tokens` / `_ocr_band_tokens` mocked.

The end-to-end check against the 4 real cromos lives in
``test_marca_image_integration.py`` (skipped unless both Tesseract
and the fixture PNGs are present).
"""

from __future__ import annotations

from itertools import pairwise
from unittest.mock import patch

import cv2
import numpy as np

from src.features.scraping.marca_image import (
    ParsedMarcaRow,
    _build_masks,
    _clean_name,
    _count_stars,
    _detect_row_centers,
    _find_column_split,
    _find_table_region,
    _has_dash,
    _is_sub_arrow,
    _parse_row_tokens,
    _strip_accents_lower,
    parse_marca_image,
)

# ---------------------------------------------------------------------------
# Pure helpers - no images
# ---------------------------------------------------------------------------


class TestStripAccentsLower:
    def test_drops_diacritics(self) -> None:
        assert _strip_accents_lower("Gutiérrez") == "gutierrez"
        assert _strip_accents_lower("Niño") == "nino"
        assert _strip_accents_lower("García-López") == "garcia-lopez"

    def test_already_clean(self) -> None:
        assert _strip_accents_lower("Pulisic") == "pulisic"

    def test_strip_whitespace(self) -> None:
        assert _strip_accents_lower("  Reyna  ") == "reyna"


class TestCleanName:
    def test_basic(self) -> None:
        assert _clean_name(["Pulisic"]) == "Pulisic"

    def test_drops_non_letters(self) -> None:
        assert _clean_name(["Reyna82'"]) == "Reyna"

    def test_lowercase_first_capitalised(self) -> None:
        assert _clean_name(["jin-gyu"]) == "Jin-gyu"

    def test_drops_short_trailing_lowercase_noise(self) -> None:
        # OCR sometimes leaves "ca" / "ti" tokens from icon labels.
        assert _clean_name(["Eustaquio", "ca"]) == "Eustaquio"

    def test_keeps_short_token_if_only_one(self) -> None:
        assert _clean_name(["Li"]) == "Li"

    def test_drops_tokens_below_2_letters(self) -> None:
        assert _clean_name(["A", "Pulisic"]) == "Pulisic"

    def test_multi_word_name_preserved(self) -> None:
        assert _clean_name(["Jonathan", "David"]) == "Jonathan David"


class TestParseRowTokens:
    def test_starter_simple(self) -> None:
        toks = [
            {"text": "10", "x": 30, "conf": 90},
            {"text": "Pulisic", "x": 80, "conf": 85},
        ]
        num, name, is_sub, minute, is_sc, conf = _parse_row_tokens(toks)
        assert (num, name, is_sub, minute, is_sc) == (10, "Pulisic", False, None, False)
        assert 0.8 < conf < 0.9

    def test_substitute_with_minute(self) -> None:
        toks = [
            {"text": "→", "x": 10, "conf": 90},
            {"text": "7", "x": 35, "conf": 90},
            {"text": "Reyna", "x": 80, "conf": 85},
            {"text": "82'", "x": 200, "conf": 80},
        ]
        num, name, is_sub, minute, _is_sc, _ = _parse_row_tokens(toks)
        assert num == 7
        assert name == "Reyna"
        assert is_sub is True
        assert minute == 82

    def test_glued_number_name(self) -> None:
        # "21Osorio" or "7_Eustaquio" - OCR fuses dorsal + name.
        toks = [{"text": "7_Eustaquio", "x": 30, "conf": 88}]
        num, name, _, _, _, _ = _parse_row_tokens(toks)
        assert num == 7
        assert name == "Eustaquio"

    def test_sc_token(self) -> None:
        toks = [
            {"text": "13", "x": 30, "conf": 90},
            {"text": "Chytil", "x": 80, "conf": 85},
            {"text": "s/c", "x": 250, "conf": 75},
        ]
        num, name, _, _, is_sc, _ = _parse_row_tokens(toks)
        assert num == 13
        assert name == "Chytil"
        assert is_sc is True

    def test_star_junk_ignored_for_name(self) -> None:
        toks = [
            {"text": "10", "x": 30, "conf": 90},
            {"text": "Pulisic", "x": 80, "conf": 85},
            # Tesseract sometimes reads ★★★ as "kkk" / "***".
            {"text": "kkk", "x": 220, "conf": 60},
        ]
        _, name, _, _, _, _ = _parse_row_tokens(toks)
        assert name == "Pulisic"

    def test_empty_tokens(self) -> None:
        num, name, is_sub, minute, is_sc, conf = _parse_row_tokens([])
        assert (num, name, is_sub, minute, is_sc, conf) == (None, "", False, None, False, 0.0)

    def test_arrow_late_in_row_does_not_mark_sub(self) -> None:
        # The arrow keyword must be left-aligned (x < 60); otherwise
        # it could be a stylised character inside the name.
        toks = [
            {"text": "10", "x": 30, "conf": 90},
            {"text": "Pulisic", "x": 80, "conf": 85},
            {"text": "→", "x": 200, "conf": 70},
        ]
        _, _, is_sub, _, _, _ = _parse_row_tokens(toks)
        assert is_sub is False


# ---------------------------------------------------------------------------
# CV helpers - synthetic numpy images
# ---------------------------------------------------------------------------


def _make_image(h: int, w: int, bgcolor: tuple[int, int, int] = (255, 255, 255)) -> np.ndarray:
    """White BGR image of size (h, w)."""
    return np.full((h, w, 3), bgcolor, dtype=np.uint8)


def _draw_square(img: np.ndarray, xc: int, yc: int, size: int, bgr: tuple[int, int, int]) -> None:
    """Filled square centred at (xc, yc)."""
    half = size // 2
    cv2.rectangle(img, (xc - half, yc - half), (xc + half, yc + half), bgr, thickness=-1)


def _draw_rect(
    img: np.ndarray,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    bgr: tuple[int, int, int],
) -> None:
    cv2.rectangle(img, (x0, y0), (x1, y1), bgr, thickness=-1)


class TestCountStars:
    def test_no_stars(self) -> None:
        img = _make_image(40, 200)
        red, _ = _build_masks(img)
        assert _count_stars(red, yc=20, xa=0, xb=200, sc=1.0) == 0

    def test_three_stars(self) -> None:
        img = _make_image(40, 200)
        for xc in (100, 130, 160):
            _draw_square(img, xc, 20, 8, (0, 0, 200))
        red, _ = _build_masks(img)
        assert _count_stars(red, yc=20, xa=0, xb=200, sc=1.0) == 3

    def test_capped_at_four(self) -> None:
        img = _make_image(40, 250)
        for xc in (100, 120, 140, 160, 180):
            _draw_square(img, xc, 20, 8, (0, 0, 200))
        red, _ = _build_masks(img)
        assert _count_stars(red, yc=20, xa=0, xb=250, sc=1.0) == 4

    def test_arrow_zone_excluded(self) -> None:
        img = _make_image(40, 200)
        # Blob inside the arrow zone (first 14%).
        _draw_square(img, 10, 20, 12, (0, 0, 200))
        red, _ = _build_masks(img)
        assert _count_stars(red, yc=20, xa=0, xb=200, sc=1.0) == 0

    def test_long_thin_blob_rejected(self) -> None:
        img = _make_image(40, 200)
        # 8:1 aspect ratio - not a star.
        _draw_rect(img, 100, 18, 180, 22, (0, 0, 200))
        red, _ = _build_masks(img)
        assert _count_stars(red, yc=20, xa=0, xb=200, sc=1.0) == 0


class TestHasDash:
    def test_finds_short_flat_blob(self) -> None:
        img = _make_image(40, 200)
        _draw_rect(img, 160, 19, 172, 22, (0, 0, 0))
        _, gray = _build_masks(img)
        assert _has_dash(gray, yc=20, xa=0, xb=200, sc=1.0) is True

    def test_too_tall_rejected(self) -> None:
        img = _make_image(40, 200)
        _draw_rect(img, 160, 14, 172, 24, (0, 0, 0))
        _, gray = _build_masks(img)
        assert _has_dash(gray, yc=20, xa=0, xb=200, sc=1.0) is False

    def test_in_left_half_ignored(self) -> None:
        img = _make_image(40, 200)
        _draw_rect(img, 30, 19, 42, 22, (0, 0, 0))
        _, gray = _build_masks(img)
        assert _has_dash(gray, yc=20, xa=0, xb=200, sc=1.0) is False

    def test_empty(self) -> None:
        img = _make_image(40, 200)
        _, gray = _build_masks(img)
        assert _has_dash(gray, yc=20, xa=0, xb=200, sc=1.0) is False


class TestIsSubArrow:
    def test_red_blob_at_start(self) -> None:
        img = _make_image(40, 200)
        _draw_rect(img, 5, 17, 25, 23, (0, 0, 200))
        red, _ = _build_masks(img)
        assert _is_sub_arrow(red, yc=20, xa=0, sc=1.0) is True

    def test_no_red_blob(self) -> None:
        img = _make_image(40, 200)
        red, _ = _build_masks(img)
        assert _is_sub_arrow(red, yc=20, xa=0, sc=1.0) is False

    def test_red_blob_far_right_ignored(self) -> None:
        img = _make_image(40, 200)
        _draw_rect(img, 150, 17, 175, 23, (0, 0, 200))
        red, _ = _build_masks(img)
        assert _is_sub_arrow(red, yc=20, xa=0, sc=1.0) is False


class TestFindColumnSplit:
    def test_picks_white_gutter(self) -> None:
        img = _make_image(200, 400)
        _draw_rect(img, 30, 50, 180, 150, (0, 0, 0))
        _draw_rect(img, 220, 50, 370, 150, (0, 0, 0))
        split = _find_column_split(img, 0, 200)
        # The gutter is between x=180 and x=220; centre band is
        # 168..232, so the function picks something inside the gutter.
        assert 180 <= split <= 220


class TestFindTableRegion:
    def test_red_bar_caps_bottom(self) -> None:
        img = _make_image(300, 500)
        _draw_rect(img, 0, 250, 500, 258, (0, 0, 220))
        red, _ = _build_masks(img)
        y0, y1 = _find_table_region(img, red)
        assert y0 == int(300 * 0.16)
        assert y1 == 250

    def test_no_red_bar_falls_through_to_bottom(self) -> None:
        img = _make_image(300, 500)
        red, _ = _build_masks(img)
        _, y1 = _find_table_region(img, red)
        assert y1 == 300


# ---------------------------------------------------------------------------
# Row anchoring - mock _ocr_column_tokens
# ---------------------------------------------------------------------------


class TestDetectRowCenters:
    """Pure anchor/pitch/fill logic, OCR mocked away."""

    def test_simple_three_anchors_no_gap(self) -> None:
        tokens = [
            {"text": "10", "x": 5, "y": 14, "w": 10, "conf": 90},
            {"text": "11", "x": 5, "y": 34, "w": 10, "conf": 90},
            {"text": "12", "x": 5, "y": 54, "w": 10, "conf": 90},
        ]
        col = np.zeros((80, 50), dtype=np.uint8)
        with patch(
            "src.features.scraping.marca_image._ocr_column_tokens",
            return_value=tokens,
        ):
            centers = _detect_row_centers(col, col_w=50, sc=1.0)
        nums = [c[1] for c in centers]
        assert 10 in nums and 11 in nums and 12 in nums
        ys = [c[0] for c in centers]
        diffs = [b - a for a, b in pairwise(ys)]
        for d in diffs:
            assert 14 <= d <= 26

    def test_fills_interior_gap(self) -> None:
        # 4 anchors: #10, #11, #12 sit 20 px apart so the median pitch
        # is 20. #14 is 40 px past #12 (gap = 2x pitch) so one
        # interpolated row gets inserted between them.
        tokens = [
            {"text": "10", "x": 5, "y": 14, "w": 10, "conf": 90},  # → y=20
            {"text": "11", "x": 5, "y": 34, "w": 10, "conf": 90},  # → y=40
            {"text": "12", "x": 5, "y": 54, "w": 10, "conf": 90},  # → y=60
            {"text": "14", "x": 5, "y": 94, "w": 10, "conf": 90},  # → y=100 (gap=40)
        ]
        col = np.zeros((130, 50), dtype=np.uint8)
        with patch(
            "src.features.scraping.marca_image._ocr_column_tokens",
            return_value=tokens,
        ):
            centers = _detect_row_centers(col, col_w=50, sc=1.0)
        anchors = [c for c in centers if c[1] is not None]
        gap_fills = [c for c in centers if c[1] is None]
        assert len(anchors) == 4
        assert len(gap_fills) >= 1
        # Interpolated row should sit around y=80 (between #12 @ 60 and #14 @ 100).
        assert any(75 <= y <= 85 for y, num in centers if num is None)

    def test_drops_tokens_outside_left_third(self) -> None:
        # Anchor x must be < col_w/3. A digit token at x=40 (80% of
        # col_w) is a name-like misread, not a jersey number.
        tokens = [
            {"text": "10", "x": 5, "y": 14, "w": 10, "conf": 90},
            {"text": "11", "x": 40, "y": 34, "w": 10, "conf": 90},
            {"text": "12", "x": 5, "y": 54, "w": 10, "conf": 90},
        ]
        col = np.zeros((80, 50), dtype=np.uint8)
        with patch(
            "src.features.scraping.marca_image._ocr_column_tokens",
            return_value=tokens,
        ):
            centers = _detect_row_centers(col, col_w=50, sc=1.0)
        nums = [c[1] for c in centers]
        assert 11 not in nums

    def test_extends_below_last_anchor(self) -> None:
        tokens = [
            {"text": "10", "x": 5, "y": 14, "w": 10, "conf": 90},
            {"text": "11", "x": 5, "y": 34, "w": 10, "conf": 90},
        ]
        col = np.zeros((80, 50), dtype=np.uint8)
        with patch(
            "src.features.scraping.marca_image._ocr_column_tokens",
            return_value=tokens,
        ):
            centers = _detect_row_centers(col, col_w=50, sc=1.0)
        assert any(c[0] > 40 for c in centers)


# ---------------------------------------------------------------------------
# End-to-end with mocked OCR
# ---------------------------------------------------------------------------


class TestParseMarcaImage:
    def test_empty_bytes_returns_empty(self) -> None:
        assert parse_marca_image(b"") == []

    def test_invalid_bytes_returns_empty(self) -> None:
        assert parse_marca_image(b"not an image") == []

    def test_full_pipeline_with_mocked_ocr(self) -> None:
        """Tiny synthetic cromo + both OCR passes mocked.

        Image is 200 (h) by 400 (w). Footer red bar at y=170-180 so
        `_find_table_region` returns y0=32 (= 200·0.16), y1=170.
        The left-column OCR anchor at token.y=50 maps to
        ``center.y = 50 + 6 = 56`` in strip coordinates, or
        ``y_abs = 56 + 32 = 88`` in image coordinates — that's where
        we paint the red stars so `_count_stars` finds them.
        """
        img = _make_image(200, 400)
        _draw_rect(img, 0, 170, 400, 180, (0, 0, 220))
        # Red stars at y=88, x=80/100/120, well inside the LEFT column
        # (column split is auto-detected ~ x=168, so anything past that
        # would leak into the away column).
        for xc in (80, 100, 120):
            _draw_square(img, xc, 88, 8, (0, 0, 200))

        call_state = {"col_calls": 0}

        def fake_col_ocr(green_col: np.ndarray) -> list[dict]:
            # First column processed is the LEFT one (parser iterates
            # columns in order). Only the left gets the anchor.
            call_state["col_calls"] += 1
            if call_state["col_calls"] == 1:
                return [{"text": "10", "x": 8, "y": 50, "w": 10, "conf": 90}]
            return []

        def fake_band_ocr(
            green_full: np.ndarray, yc: int, xa: int, xb: int, sc: float
        ) -> list[dict]:
            if xa < 100:
                return [
                    {"text": "10", "x": 5, "conf": 88},
                    {"text": "Pulisic", "x": 30, "conf": 85},
                ]
            return []

        ok, buf = cv2.imencode(".png", img)
        assert ok
        png_bytes = bytes(buf)

        with (
            patch(
                "src.features.scraping.marca_image._ocr_column_tokens",
                side_effect=fake_col_ocr,
            ),
            patch(
                "src.features.scraping.marca_image._ocr_band_tokens",
                side_effect=fake_band_ocr,
            ),
        ):
            rows = parse_marca_image(png_bytes)

        pulisic = next((r for r in rows if r.surname_clean == "pulisic"), None)
        assert pulisic is not None
        assert pulisic.stars == 3
        assert pulisic.explicit_marker is None
        assert pulisic.dorsal == 10


# ---------------------------------------------------------------------------
# ParsedMarcaRow dataclass shape - service.marca_preview depends on it
# ---------------------------------------------------------------------------


def test_parsed_marca_row_has_stable_shape() -> None:
    row = ParsedMarcaRow(
        raw_text="10 Pulisic",
        surname_clean="pulisic",
        stars=3,
        is_substitute=False,
        minute=None,
        confidence=0.9,
        explicit_marker=None,
        dorsal=10,
    )
    assert row.surname_clean == "pulisic"
    assert row.stars == 3
    assert row.is_substitute is False
    assert row.minute is None
    assert row.explicit_marker is None
    assert row.dorsal == 10
