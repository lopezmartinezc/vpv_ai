"""Ground-truth bench for the Marca cromo parser.

Ports `gt_check.py` from the standalone reference kit. Runs
`parse_marca_image` against 3 real cromos and verifies the rating
extracted for every player against a verified-by-pixel ground truth.

The reference extractor scores 94/94 (100%) here. This bench is the
no-regression gate for any future change to the rating detectors
(`_count_stars`, `_has_dash`) or the row-anchoring pipeline.

Skipped when:
- Tesseract is not installed.
- The fixture PNGs are not present (e.g. CI without them committed).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import cv2
import numpy as np
import pytest

from src.features.scraping.marca_image import (
    _REF_WIDTH,
    ParsedMarcaRow,
    _build_masks,
    _count_stars,
    _detect_row_centers,
    _find_column_split,
    _find_table_region,
    _has_dash,
    _is_sub_arrow,
    _ocr_band_tokens,
    _parse_row_tokens,
    parse_marca_image,
)

_FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "marca"


def _tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


# Ground truth, per-fixture, per-side, per-dorsal:
#   int N  -> N stars
#   "-"    -> dash (jugó mal, -1)
#   "SC"   -> empty cell / s/c (jugó poco, 0)
#
# These were verified at the pixel level on the original cromos. See
# the BRIEF in the reference kit for the discussion of Arce #18 (SC,
# not "-"), which is the canonical "easy to get wrong" case.
_GROUND_TRUTH: dict[str, dict[str, dict[int, object]]] = {
    "marca.png": {  # Mexico 2-0 Sudáfrica
        "home": {
            1: 2,
            15: 1,
            3: 1,
            5: 2,
            23: 1,
            6: 2,
            4: 1,
            8: 2,
            19: 1,
            26: 1,
            24: 1,
            25: 1,
            9: 2,
            14: 1,
            16: 3,
            10: 1,
        },
        "away": {
            1: "-",
            20: 1,
            21: 1,
            19: "-",
            14: "-",
            6: 1,
            7: 1,
            4: 1,
            13: "-",
            23: "-",
            11: "-",
            9: "-",
            5: 1,
            15: "-",
            17: 1,
        },
    },
    "img_a.jpeg": {  # Canada 1-1 Bosnia
        "home": {
            16: 1,
            2: 1,
            4: 1,
            13: 1,
            22: 1,
            17: 1,
            20: 1,
            8: 1,
            7: 2,
            21: "SC",
            11: 2,
            14: 1,
            10: 1,
            24: 1,
            12: 1,
            9: 2,
        },
        "away": {
            1: 1,
            7: 1,
            18: 2,
            4: 1,
            5: 2,
            17: "SC",
            20: 1,
            14: 1,
            13: 1,
            8: 1,
            6: 1,
            15: 1,
            19: 1,
            10: 1,
            25: 2,
            9: 1,
        },
    },
    "img_d.png": {  # USA 4-1 Paraguay
        "home": {
            24: 1,
            16: 2,
            3: 2,
            13: 2,
            5: 2,
            17: 2,
            7: 2,
            4: 2,
            2: 2,
            21: 1,
            8: 2,
            10: 3,
            14: 1,
            20: 3,
            9: 1,
        },
        "away": {
            12: "-",
            4: "-",
            2: "SC",
            15: "-",
            3: "-",
            6: "-",
            16: "-",
            11: 1,
            14: "-",
            8: "-",
            17: "SC",
            10: "-",
            7: "SC",
            9: "-",
            18: "SC",
            19: 1,
        },
    },
}


def _parse_by_columns(
    png_bytes: bytes,
) -> tuple[dict[int, object], dict[int, object]]:
    """Re-run the parser pipeline column-by-column for the bench.

    `parse_marca_image` flattens both columns into one list and only
    exposes the dorsal back — no column tag. Without that, a player
    whose dorsal is missing from the home roster but present in the
    away (e.g. GK #1 vs GK #16) cannot be bucketed back to its team.
    This helper replays the same pipeline but groups by column, which
    is exactly what the production service does via the home/away
    roster lookups.
    """
    arr = np.frombuffer(png_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    assert img is not None
    red, gray = _build_masks(img)
    _h_img, w_img = img.shape[:2]
    sc = w_img / _REF_WIDTH
    y0, y1 = _find_table_region(img, red)
    split = _find_column_split(img, y0, y1)
    green = img[:, :, 1]

    sides: dict[str, dict[int, object]] = {"home": {}, "away": {}}
    for side, xa, xb in [("home", 0, split), ("away", split, w_img)]:
        col_green = green[y0:y1, xa:xb]
        centers = _detect_row_centers(col_green, xb - xa, sc)
        seen: set[int] = set()
        for cy, anchor_num in centers:
            yc = cy + y0
            toks = _ocr_band_tokens(green, yc, xa, xb, sc)
            num, _name, _is_sub, _minute, is_sc, _conf = _parse_row_tokens(toks)
            if anchor_num is not None:
                num = anchor_num
            if num is None or num in seen:
                continue
            seen.add(num)

            rating: int | str
            if is_sc:
                rating = "SC"
            else:
                stars = _count_stars(red, yc, xa, xb, sc)
                if stars > 0:
                    rating = stars
                elif _has_dash(gray, yc, xa, xb, sc):
                    rating = "-"
                else:
                    rating = "SC"
            # is_sub kept available via _is_sub_arrow if we ever want
            # to bench substitutions too; not needed for ratings.
            _ = _is_sub_arrow(red, yc, xa, sc)
            sides[side][num] = rating
    return sides["home"], sides["away"]


def _row_to_rating(row: ParsedMarcaRow) -> int | str:
    """Convert ParsedMarcaRow -> ground-truth shape (int | '-' | 'SC')."""
    if row.stars > 0:
        return row.stars
    if row.explicit_marker == "dash":
        return "-"
    return "SC"


@pytest.mark.skipif(not _tesseract_available(), reason="tesseract not installed")
@pytest.mark.parametrize("fixture_name", sorted(_GROUND_TRUTH.keys()))
def test_parse_marca_image_ground_truth(fixture_name: str) -> None:
    """Per-fixture rating accuracy must be 100%.

    Validated locally at 94/94 across the 3 fixtures (matches the
    reference extractor). Any drop below 100% is a regression in
    `_count_stars`, `_has_dash`, or `_detect_row_centers` — investigate
    BEFORE relaxing this gate.
    """
    fixture = _FIXTURE_DIR / fixture_name
    if not fixture.exists():
        pytest.skip(f"fixture {fixture_name} not present")

    png_bytes = fixture.read_bytes()
    rows = parse_marca_image(png_bytes)
    assert rows, f"{fixture_name}: parser returned no rows"

    home_got, away_got = _parse_by_columns(png_bytes)
    expected = _GROUND_TRUTH[fixture_name]

    total = 0
    correct = 0
    misses: list[str] = []
    for side, side_gt in expected.items():
        side_got = home_got if side == "home" else away_got
        for dorsal, exp_rating in side_gt.items():
            total += 1
            got = side_got.get(dorsal, "ABSENT")
            if got == exp_rating:
                correct += 1
            else:
                misses.append(f"  {fixture_name} {side} #{dorsal}: got={got!r} exp={exp_rating!r}")

    accuracy = correct / total
    msg = f"{fixture_name}: {correct}/{total} ratings correct ({accuracy:.1%})" + (
        "\n" + "\n".join(misses) if misses else ""
    )
    assert correct == total, msg


@pytest.mark.skipif(not _tesseract_available(), reason="tesseract not installed")
def test_no_row_loss() -> None:
    """No fixture should drop more than 2 players (out of ~30)."""
    for fixture_name, expected in _GROUND_TRUTH.items():
        fixture = _FIXTURE_DIR / fixture_name
        if not fixture.exists():
            continue
        png_bytes = fixture.read_bytes()
        rows = parse_marca_image(png_bytes)
        expected_count = sum(len(side_gt) for side_gt in expected.values())
        got_count = sum(1 for r in rows if r.dorsal is not None)
        loss = expected_count - got_count
        assert loss <= 2, (
            f"{fixture_name}: dropped {loss} rows (expected {expected_count}, got {got_count})"
        )
