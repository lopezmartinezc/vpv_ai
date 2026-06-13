"""Tests for the Marca cromo image parser.

`_parse_row_text`, `_count_red_stars_in_bbox`, `_detect_text_rows`,
and `_split_columns` are unit-tested directly — none need Tesseract
running. `parse_marca_image` is exercised against a synthetic image
with `_ocr_single_line` mocked so CI doesn't need the system binary
installed.

The fuzzy-fallback logic lives in `ScrapingService.marca_preview`
and is covered by a difflib-based smoke test at the bottom.
"""

from __future__ import annotations

import difflib
from io import BytesIO
from unittest.mock import patch

from PIL import Image, ImageDraw

from src.features.scraping.marca_image import (
    _count_red_stars_in_bbox,
    _detect_right_marker,
    _detect_text_rows,
    _find_red_bar_top_y,
    _find_top_divider_y,
    _parse_row_text,
    _split_columns,
    parse_marca_image,
)

# ---------------------------------------------------------------------------
# Row-text parser
# ---------------------------------------------------------------------------


class TestParseRowText:
    def test_starter_with_stars_in_text(self) -> None:
        surname, is_sub, minute = _parse_row_text("10 Pulisic ★★★")
        assert surname == "pulisic"
        assert is_sub is False
        assert minute is None

    def test_starter_no_marks(self) -> None:
        surname, is_sub, minute = _parse_row_text("24 Freese")
        assert surname == "freese"
        assert is_sub is False
        assert minute is None

    def test_starter_with_substitution_minute(self) -> None:
        surname, is_sub, minute = _parse_row_text("→ 7 Reyna 82'")
        assert surname == "reyna"
        assert is_sub is True
        assert minute == 82

    def test_arrow_ascii_fallback(self) -> None:
        surname, is_sub, _ = _parse_row_text("-> 14 Berhalter 45'")
        assert surname == "berhalter"
        assert is_sub is True

    def test_accents_are_folded(self) -> None:
        surname, _, _ = _parse_row_text("4 Cáceres")
        assert surname == "caceres"

    def test_compound_surname_keeps_last_token(self) -> None:
        surname, _, _ = _parse_row_text("17 Brian Gutiérrez 65'")
        assert surname == "gutierrez"

    def test_empty_input_returns_empty_surname(self) -> None:
        surname, is_sub, minute = _parse_row_text("")
        assert surname == ""
        assert is_sub is False
        assert minute is None

    def test_only_numbers_and_punct_returns_empty(self) -> None:
        surname, _, _ = _parse_row_text("12 5'")
        assert surname == ""


# ---------------------------------------------------------------------------
# Star counter on synthetic images
# ---------------------------------------------------------------------------


def _make_image_with_red_blobs(
    width: int, height: int, blobs: list[tuple[int, int, int]]
) -> Image.Image:
    img = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    for cx, cy, r in blobs:
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(200, 30, 30))
    return img


class TestCountRedStars:
    def test_no_blobs(self) -> None:
        img = Image.new("RGB", (200, 40), (255, 255, 255))
        assert _count_red_stars_in_bbox(img, (0, 0, 200, 40)) == 0

    def test_three_distinct_blobs(self) -> None:
        img = _make_image_with_red_blobs(200, 40, [(40, 20, 6), (90, 20, 6), (140, 20, 6)])
        assert _count_red_stars_in_bbox(img, (0, 0, 200, 40)) == 3

    def test_caps_at_four(self) -> None:
        img = _make_image_with_red_blobs(
            300, 40, [(40, 20, 6), (80, 20, 6), (120, 20, 6), (160, 20, 6), (200, 20, 6)]
        )
        assert _count_red_stars_in_bbox(img, (0, 0, 300, 40)) == 4

    def test_tiny_red_specks_are_ignored(self) -> None:
        img = Image.new("RGB", (200, 40), (255, 255, 255))
        img.putpixel((50, 20), (200, 30, 30))
        img.putpixel((100, 20), (200, 30, 30))
        assert _count_red_stars_in_bbox(img, (0, 0, 200, 40)) == 0

    def test_bbox_outside_image_is_clipped(self) -> None:
        img = _make_image_with_red_blobs(200, 40, [(40, 20, 6)])
        assert _count_red_stars_in_bbox(img, (300, 0, 400, 40)) == 0


# ---------------------------------------------------------------------------
# Column splitter
# ---------------------------------------------------------------------------


class TestSplitColumns:
    def test_halves_at_mid(self) -> None:
        img = Image.new("RGB", (200, 100), (255, 255, 255))
        left, right = _split_columns(img)
        assert left.size == (100, 100)
        assert right.size == (100, 100)

    def test_odd_width(self) -> None:
        # 201 px wide → left should be 100, right should be 101.
        img = Image.new("RGB", (201, 50), (255, 255, 255))
        left, right = _split_columns(img)
        assert left.size == (100, 50)
        assert right.size == (101, 50)


# ---------------------------------------------------------------------------
# Row detector (horizontal density)
# ---------------------------------------------------------------------------


def _draw_text_band(img: Image.Image, y0: int, y1: int, dark_fraction: float = 0.5) -> None:
    """Fill a horizontal band with dark pixels every ``1/dark_fraction``.

    Uses a fill that matches the image mode (grayscale or RGB).
    """
    draw = ImageDraw.Draw(img)
    step = max(1, int(1 / max(0.01, dark_fraction)))
    fill = 40 if img.mode == "L" else (40, 40, 40)
    for x in range(0, img.width, step):
        draw.line((x, y0, x, y1 - 1), fill=fill)


class TestDetectTextRows:
    def test_picks_up_three_bands(self) -> None:
        img = Image.new("L", (200, 200), 255)
        _draw_text_band(img, 30, 50, dark_fraction=0.3)
        _draw_text_band(img, 80, 100, dark_fraction=0.3)
        _draw_text_band(img, 130, 150, dark_fraction=0.3)
        bands = _detect_text_rows(img)
        assert len(bands) == 3
        # Sanity-check the first band roughly matches what we drew.
        y0, y1 = bands[0]
        assert 28 <= y0 <= 32
        assert 48 <= y1 <= 52

    def test_filters_out_tall_header(self) -> None:
        img = Image.new("L", (200, 300), 255)
        # 100-pixel tall band (the title block) — should be discarded.
        _draw_text_band(img, 10, 110, dark_fraction=0.3)
        # And a normal row.
        _draw_text_band(img, 150, 170, dark_fraction=0.3)
        bands = _detect_text_rows(img)
        assert len(bands) == 1
        y0, _ = bands[0]
        assert 148 <= y0 <= 152

    def test_filters_out_micro_noise(self) -> None:
        img = Image.new("L", (200, 100), 255)
        # 2 px tall band — below _MIN_ROW_HEIGHT.
        _draw_text_band(img, 30, 32, dark_fraction=0.3)
        bands = _detect_text_rows(img)
        assert bands == []

    def test_empty_image(self) -> None:
        img = Image.new("L", (200, 100), 255)
        bands = _detect_text_rows(img)
        assert bands == []


# ---------------------------------------------------------------------------
# End-to-end parse_marca_image with mocked single-line OCR
# ---------------------------------------------------------------------------


def _png_bytes_with_layout(
    width: int, height: int, left_rows: list[tuple[int, int]], right_rows: list[tuple[int, int]]
) -> bytes:
    """Build a synthetic two-column cromo. rows = list of (y0, y1) bands.

    Both columns get dark text bands; we don't bother drawing stars
    here because the OCR is mocked.
    """
    img = Image.new("RGB", (width, height), (255, 255, 255))
    mid = width // 2
    for y0, y1 in left_rows:
        draw = ImageDraw.Draw(img)
        for x in range(0, mid, 3):
            draw.line((x, y0, x, y1 - 1), fill=(40, 40, 40))
    for y0, y1 in right_rows:
        draw = ImageDraw.Draw(img)
        for x in range(mid, width, 3):
            draw.line((x, y0, x, y1 - 1), fill=(40, 40, 40))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestParseMarcaImageWithMockedOcr:
    def test_empty_bytes_returns_empty_list(self) -> None:
        assert parse_marca_image(b"") == []

    def test_two_columns_one_row_each(self) -> None:
        png = _png_bytes_with_layout(
            width=400,
            height=200,
            left_rows=[(40, 70)],
            right_rows=[(40, 70)],
        )
        # Mock returns one surname for left, another for right.
        seq = iter([("10 Pulisic", 0.92), ("→ 7 Reyna 82'", 0.87)])

        def fake_ocr(_img, lang: str = "spa") -> tuple[str, float]:
            return next(seq)

        with patch("src.features.scraping.marca_image._ocr_single_line", side_effect=fake_ocr):
            rows = parse_marca_image(png)

        assert len(rows) == 2
        assert rows[0].surname_clean == "pulisic"
        assert rows[0].is_substitute is False
        assert rows[1].surname_clean == "reyna"
        assert rows[1].is_substitute is True
        assert rows[1].minute == 82

    def test_rows_without_surname_are_dropped(self) -> None:
        png = _png_bytes_with_layout(
            width=400,
            height=200,
            left_rows=[(40, 70)],
            right_rows=[(40, 70)],
        )
        with patch(
            "src.features.scraping.marca_image._ocr_single_line",
            side_effect=[("12 5'", 0.3), ("", 0.0)],
        ):
            rows = parse_marca_image(png)
        assert rows == []


# ---------------------------------------------------------------------------
# Fuzzy fallback (mirrors the contract used in ScrapingService.marca_preview)
# ---------------------------------------------------------------------------


_FUZZY_CUTOFF = 0.78
_FUZZY_ROSTER = (
    "pulisic",
    "balogun",
    "freese",
    "tillman",
    "reyna",
    "bobadilla",
    "almiron",
    "gomez",
    "alderete",
    "gill",
)


def _close_fuzzy(ocr: str) -> list[str]:
    return difflib.get_close_matches(ocr, _FUZZY_ROSTER, n=1, cutoff=_FUZZY_CUTOFF)


class TestSurnameFuzzyFallback:
    def test_one_letter_off_matches(self) -> None:
        assert _close_fuzzy("plisic") == ["pulisic"]
        assert _close_fuzzy("balogn") == ["balogun"]
        assert _close_fuzzy("freesee") == ["freese"]

    def test_too_different_does_not_match(self) -> None:
        assert _close_fuzzy("messi") == []
        assert _close_fuzzy("ronaldo") == []

    def test_exact_match_still_returned(self) -> None:
        assert _close_fuzzy("pulisic") == ["pulisic"]


# ---------------------------------------------------------------------------
# Image-strip detectors (red bar at bottom, divider line at top)
# ---------------------------------------------------------------------------


class TestFindRedBarTopY:
    def test_detects_full_width_red_band(self) -> None:
        # 200x400 image with a red 20-px tall bar at y=300.
        img = Image.new("RGB", (200, 400), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.rectangle((0, 300, 199, 319), fill=(220, 30, 30))
        # `y=300` is the top edge of the bar — that's what we want.
        assert _find_red_bar_top_y(img) == 300

    def test_returns_none_when_no_bar(self) -> None:
        # Lots of small red blobs (like stars) — none span the full width.
        img = _make_image_with_red_blobs(200, 400, [(40, 100, 6), (90, 100, 6), (140, 100, 6)])
        assert _find_red_bar_top_y(img) is None

    def test_takes_lowest_bar_when_two_exist(self) -> None:
        # If the title block happened to contain a red strip (shouldn't,
        # but be defensive), we want the LAST one going from bottom up.
        img = Image.new("RGB", (200, 400), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.rectangle((0, 50, 199, 60), fill=(220, 30, 30))
        draw.rectangle((0, 300, 199, 319), fill=(220, 30, 30))
        # The bottom bar starts at y=300 and we scan upward; we should
        # return the top of THAT bar, not the title's.
        assert _find_red_bar_top_y(img) == 300


class TestFindTopDividerY:
    def test_detects_thin_black_line(self) -> None:
        # 200x300 with a 2-px tall black line at y=60.
        img = Image.new("L", (200, 300), 255)
        draw = ImageDraw.Draw(img)
        draw.rectangle((0, 60, 199, 61), fill=0)
        # The function returns the y just BELOW the divider so the
        # caller can crop without clipping the first player row.
        y = _find_top_divider_y(img)
        assert y is not None
        assert 61 <= y <= 63

    def test_ignores_text_band(self) -> None:
        # A regular text band — dense but ~20 px tall — should NOT be
        # treated as a divider.
        img = Image.new("L", (200, 300), 255)
        _draw_text_band(img, 30, 50, dark_fraction=0.6)
        # Density is high but band is way taller than the divider.
        assert _find_top_divider_y(img) is None

    def test_only_looks_in_upper_third(self) -> None:
        # A thin black line in the bottom half is ignored.
        img = Image.new("L", (200, 300), 255)
        draw = ImageDraw.Draw(img)
        draw.rectangle((0, 250, 199, 251), fill=0)
        assert _find_top_divider_y(img) is None


# ---------------------------------------------------------------------------
# Right-side marker OCR (s/c, dash)
# ---------------------------------------------------------------------------


class TestDetectRightMarker:
    """The OCR call is mocked because CI has no Tesseract installed."""

    def test_sc_text_returns_sc(self) -> None:
        # The whitelist may give us a slash so the raw output is "s/c".
        with patch("pytesseract.image_to_string", return_value="s/c\n"):
            assert _detect_right_marker(Image.new("RGB", (40, 20), (255, 255, 255))) == "sc"

    def test_uppercase_sc_is_normalised(self) -> None:
        with patch("pytesseract.image_to_string", return_value="SC"):
            assert _detect_right_marker(Image.new("RGB", (40, 20), (255, 255, 255))) == "sc"

    def test_em_dash_returns_dash(self) -> None:
        with patch("pytesseract.image_to_string", return_value="—\n"):
            assert _detect_right_marker(Image.new("RGB", (40, 20), (255, 255, 255))) == "dash"

    def test_minus_sign_returns_dash(self) -> None:
        with patch("pytesseract.image_to_string", return_value="−"):  # noqa: RUF001
            assert _detect_right_marker(Image.new("RGB", (40, 20), (255, 255, 255))) == "dash"

    def test_hyphen_returns_dash(self) -> None:
        with patch("pytesseract.image_to_string", return_value="- "):
            assert _detect_right_marker(Image.new("RGB", (40, 20), (255, 255, 255))) == "dash"

    def test_empty_ocr_returns_none(self) -> None:
        with patch("pytesseract.image_to_string", return_value=""):
            assert _detect_right_marker(Image.new("RGB", (40, 20), (255, 255, 255))) is None

    def test_unknown_text_returns_none(self) -> None:
        with patch("pytesseract.image_to_string", return_value="xyz"):
            assert _detect_right_marker(Image.new("RGB", (40, 20), (255, 255, 255))) is None

    def test_empty_image_short_circuits(self) -> None:
        # An empty bbox would result in a 0x0 crop — must not call OCR.
        assert _detect_right_marker(Image.new("RGB", (0, 0), (255, 255, 255))) is None
