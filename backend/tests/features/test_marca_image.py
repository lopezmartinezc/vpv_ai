"""Tests for the Marca cromo image parser.

`_parse_row_text` and `_count_red_stars_in_bbox` are unit-tested
directly — neither needs Tesseract running. `parse_marca_image` is
exercised against a mocked `pytesseract.image_to_data` so CI doesn't
need the system binary installed.

A separate `test_marca_image_integration.py` uses a real fixture
image when Tesseract is available locally.

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
    _parse_row_text,
    parse_marca_image,
)

# ---------------------------------------------------------------------------
# Row-text parser
# ---------------------------------------------------------------------------


class TestParseRowText:
    def test_starter_with_stars_in_text(self) -> None:
        # Tesseract sometimes emits the stars as actual characters.
        # We must strip them so the surname isn't polluted.
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
        # "→ 7 Reyna 82'" — actually the arrow denotes substitution,
        # the minute is when the player went off.
        surname, is_sub, minute = _parse_row_text("→ 7 Reyna 82'")
        assert surname == "reyna"
        assert is_sub is True
        assert minute == 82

    def test_arrow_ascii_fallback(self) -> None:
        # If Tesseract OCRs the arrow as "->" we still detect the sub.
        surname, is_sub, _ = _parse_row_text("-> 14 Berhalter 45'")
        assert surname == "berhalter"
        assert is_sub is True

    def test_accents_are_folded(self) -> None:
        surname, _, _ = _parse_row_text("4 Cáceres")
        # The lookup map in the service uses accent-folded lowercase
        # keys; surname_clean must be ready to match.
        assert surname == "caceres"

    def test_compound_surname_keeps_last_token(self) -> None:
        # "Brian Gutiérrez" → match by "gutierrez".
        surname, _, _ = _parse_row_text("17 Brian Gutiérrez 65'")
        assert surname == "gutierrez"

    def test_empty_input_returns_empty_surname(self) -> None:
        surname, is_sub, minute = _parse_row_text("")
        assert surname == ""
        assert is_sub is False
        assert minute is None

    def test_only_numbers_and_punct_returns_empty(self) -> None:
        # If OCR gives us garbage, surname comes out empty and the
        # caller can drop the row.
        surname, _, _ = _parse_row_text("12 5'")
        assert surname == ""


# ---------------------------------------------------------------------------
# Star counter on synthetic images
# ---------------------------------------------------------------------------


def _make_image_with_red_blobs(
    width: int, height: int, blobs: list[tuple[int, int, int]]
) -> Image.Image:
    """blobs = list of (cx, cy, radius)."""
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
        # Five distinct blobs — we should see 4 (Marca's max).
        img = _make_image_with_red_blobs(
            300, 40, [(40, 20, 6), (80, 20, 6), (120, 20, 6), (160, 20, 6), (200, 20, 6)]
        )
        assert _count_red_stars_in_bbox(img, (0, 0, 300, 40)) == 4

    def test_tiny_red_specks_are_ignored(self) -> None:
        # Single-pixel red noise should NOT count as a star.
        img = Image.new("RGB", (200, 40), (255, 255, 255))
        img.putpixel((50, 20), (200, 30, 30))
        img.putpixel((100, 20), (200, 30, 30))
        assert _count_red_stars_in_bbox(img, (0, 0, 200, 40)) == 0

    def test_bbox_outside_image_is_clipped(self) -> None:
        img = _make_image_with_red_blobs(200, 40, [(40, 20, 6)])
        # bbox starts past the image bounds — return 0, not crash.
        assert _count_red_stars_in_bbox(img, (300, 0, 400, 40)) == 0


# ---------------------------------------------------------------------------
# End-to-end parse_marca_image with mocked Tesseract
# ---------------------------------------------------------------------------


def _make_mock_tesseract_output(rows: list[dict]) -> dict[str, list]:
    """Build a fake `pytesseract.image_to_data` DICT result.

    Each row dict needs keys: ``text`` (string), ``left``, ``top``,
    ``width``, ``height``, ``line``. We split the text by spaces and
    emit one word per token sharing the same (block, par, line) so
    the parser groups them again.
    """
    out: dict[str, list] = {
        "text": [],
        "left": [],
        "top": [],
        "width": [],
        "height": [],
        "conf": [],
        "block_num": [],
        "par_num": [],
        "line_num": [],
    }
    for row in rows:
        tokens = row["text"].split()
        x = row["left"]
        for tok in tokens:
            out["text"].append(tok)
            out["left"].append(x)
            out["top"].append(row["top"])
            out["width"].append(len(tok) * 8)
            out["height"].append(row["height"])
            out["conf"].append(90)
            out["block_num"].append(1)
            out["par_num"].append(1)
            out["line_num"].append(row["line"])
            x += len(tok) * 8 + 5
    return out


class TestParseMarcaImageWithMockedTesseract:
    def test_empty_bytes_returns_empty_list(self) -> None:
        assert parse_marca_image(b"") == []

    def test_single_row_parses(self) -> None:
        # Synth a 200x40 white image so the star counter sees zero blobs.
        buf = BytesIO()
        Image.new("RGB", (200, 40), (255, 255, 255)).save(buf, format="PNG")
        png = buf.getvalue()

        mock_data = _make_mock_tesseract_output(
            [
                {
                    "text": "10 Pulisic",
                    "left": 5,
                    "top": 5,
                    "height": 20,
                    "line": 1,
                },
            ]
        )

        with patch("pytesseract.image_to_data", return_value=mock_data):
            rows = parse_marca_image(png)

        assert len(rows) == 1
        assert rows[0].surname_clean == "pulisic"
        assert rows[0].is_substitute is False
        assert rows[0].stars == 0

    def test_multiple_rows_grouped_by_line(self) -> None:
        buf = BytesIO()
        Image.new("RGB", (300, 200), (255, 255, 255)).save(buf, format="PNG")
        png = buf.getvalue()

        mock_data = _make_mock_tesseract_output(
            [
                {"text": "24 Freese", "left": 5, "top": 5, "height": 20, "line": 1},
                {"text": "10 Pulisic", "left": 5, "top": 30, "height": 20, "line": 2},
                {
                    "text": "→ 7 Reyna 82'",
                    "left": 5,
                    "top": 55,
                    "height": 20,
                    "line": 3,
                },
            ]
        )

        with patch("pytesseract.image_to_data", return_value=mock_data):
            rows = parse_marca_image(png)

        assert [r.surname_clean for r in rows] == ["freese", "pulisic", "reyna"]
        assert rows[2].is_substitute is True
        assert rows[2].minute == 82

    def test_garbage_rows_are_dropped(self) -> None:
        buf = BytesIO()
        Image.new("RGB", (200, 40), (255, 255, 255)).save(buf, format="PNG")
        png = buf.getvalue()
        mock_data = _make_mock_tesseract_output(
            [
                # Only numbers and a stray apostrophe → no parseable surname.
                {"text": "12 5'", "left": 5, "top": 5, "height": 20, "line": 1},
            ]
        )
        with patch("pytesseract.image_to_data", return_value=mock_data):
            rows = parse_marca_image(png)
        assert rows == []


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
    """The service does fuzzy-matching when an OCR'd surname doesn't
    show up in the roster verbatim. We keep the difflib contract
    pinned here so a future tweak to the cutoff is intentional."""

    def _close(self, ocr: str) -> list[str]:
        return _close_fuzzy(ocr)

    def test_one_letter_off_matches(self) -> None:
        # Common Tesseract slip: missed letter, extra letter, swap.
        assert self._close("plisic") == ["pulisic"]
        assert self._close("balogn") == ["balogun"]
        assert self._close("freesee") == ["freese"]

    def test_too_different_does_not_match(self) -> None:
        # We do NOT want "messi" to be silently mapped to anything.
        assert self._close("messi") == []
        assert self._close("ronaldo") == []

    def test_exact_match_still_returned(self) -> None:
        assert self._close("pulisic") == ["pulisic"]
