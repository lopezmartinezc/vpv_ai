"""Parse a Marca press-clipping image and extract per-player ratings.

The image is the kind of cromo Marca publishes after a match: two
columns (one team each) with the surname and an array of red stars
on the right. Layout example for one row:

    →  7  Reyna   82'   ★★★

This module:
1. Runs Tesseract on a preprocessed copy of the image to get word
   bounding boxes.
2. Groups words into rows by Tesseract's `line_num`.
3. For each row, parses the surname / substitution / minute markers
   from the text.
4. Counts the red stars on the right side of the row by analysing
   the original color image — Tesseract is unreliable on stylised
   ``★`` glyphs so we don't trust its output for that.

Dependencies: pytesseract (Python binding) + system Tesseract with
the Spanish language pack. See docs/MUNDIAL_SCRAPING.md for the
``apt install tesseract-ocr tesseract-ocr-spa`` step.

The parser is pure (no DB, no settings). The DB plumbing lives in
``ScrapingService.marca_preview``.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)


# Heuristic — what counts as "red" for a press-clipping star.
# Threshold tuned on the USA-Paraguay sample. Values close to white
# (background) and dark grey (text) fall outside.
_RED_R_MIN = 140
_RED_G_MAX = 110
_RED_B_MAX = 110

# Minimum connected-component area (pixels) to count as one star.
# Smaller than the typical glyph, larger than antialias dots.
_MIN_STAR_BLOB = 25

# Cap the count — Marca never prints more than 4 stars.
_MAX_STARS = 4

# Fraction of the row width that we sweep for stars (right side).
_STARS_REGION_FRACTION = 0.45


@dataclass
class ParsedMarcaRow:
    """One player extracted from the cromo image.

    Surnames are folded for matching (lowercase, accents removed) so
    the backend can hand them to the existing per-team lookup.
    """

    raw_text: str
    surname_clean: str
    stars: int
    is_substitute: bool
    minute: int | None
    confidence: float


def _strip_accents_lower(value: str) -> str:
    """Mirror the helper used in `parsers.py` for the same purpose.

    Kept local to avoid the import cycle the parsers module would
    introduce."""
    normalized = unicodedata.normalize("NFD", value)
    no_marks = "".join(c for c in normalized if not unicodedata.combining(c))
    return no_marks.lower().strip()


def _count_red_stars_in_bbox(
    img_rgb: Image.Image,
    bbox: tuple[int, int, int, int],
) -> int:
    """Count distinct red blobs inside ``bbox`` of ``img_rgb``.

    Approach: binarize "red enough" pixels, flood-fill 4-neighbourhood
    connected components, count those above ``_MIN_STAR_BLOB`` area.

    Pure Pillow, no numpy. The bbox is typically ~300x30 px so the
    pixel loop is cheap.
    """
    x0, y0, x1, y1 = bbox
    x0 = max(0, x0)
    y0 = max(0, y0)
    x1 = min(img_rgb.width, x1)
    y1 = min(img_rgb.height, y1)
    if x1 <= x0 or y1 <= y0:
        return 0

    crop = img_rgb.crop((x0, y0, x1, y1)).convert("RGB")
    w, h = crop.size
    pixels = crop.load()
    if pixels is None:
        return 0

    is_red = [[False] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            pixel = pixels[x, y]
            if not isinstance(pixel, tuple) or len(pixel) < 3:
                continue
            r, g, b = pixel[0], pixel[1], pixel[2]
            if r >= _RED_R_MIN and g <= _RED_G_MAX and b <= _RED_B_MAX:
                is_red[y][x] = True

    visited = [[False] * w for _ in range(h)]
    star_count = 0
    for y in range(h):
        for x in range(w):
            if not is_red[y][x] or visited[y][x]:
                continue
            stack: list[tuple[int, int]] = [(x, y)]
            size = 0
            while stack:
                cx, cy = stack.pop()
                if cx < 0 or cx >= w or cy < 0 or cy >= h:
                    continue
                if visited[cy][cx] or not is_red[cy][cx]:
                    continue
                visited[cy][cx] = True
                size += 1
                stack.extend([(cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)])
            if size >= _MIN_STAR_BLOB:
                star_count += 1

    return min(star_count, _MAX_STARS)


def _parse_row_text(text: str) -> tuple[str, bool, int | None]:
    """Pull (surname_clean, is_substitute, minute) out of raw row text.

    Tolerates: leading arrow markers (``→`` or ``->``), leading dorsal
    numbers, trailing ``NN'`` substitution minute. Drops any star
    glyphs Tesseract might have emitted so they don't leak into the
    surname.
    """
    is_sub = bool(re.search(r"→|->", text))
    clean = re.sub(r"→|->", "", text).strip()

    minute_match = re.search(r"(\d{1,2})'", clean)
    minute = int(minute_match.group(1)) if minute_match else None

    # Strip stars Tesseract may have read.
    clean = clean.replace("★", " ").replace("*", " ")
    # Strip minute markers from the working copy.
    clean = re.sub(r"\d{1,2}'", " ", clean)
    # Strip any standalone leading number (dorsal).
    clean = re.sub(r"^\s*\d+\s+", "", clean)
    # Collapse whitespace.
    tokens = [tok for tok in clean.split() if tok]

    surname_raw = tokens[-1] if tokens else ""
    surname_clean = _strip_accents_lower(surname_raw)
    return surname_clean, is_sub, minute


def _group_words_into_rows(data: dict[str, Any]) -> dict[tuple[int, int, int], list[int]]:
    """Group word-level Tesseract output by (block, paragraph, line).

    Discards words with empty text or negative confidence.
    """
    lines: dict[tuple[int, int, int], list[int]] = defaultdict(list)
    n = len(data.get("text", []))
    for i in range(n):
        text = (data["text"][i] or "").strip()
        if not text:
            continue
        # `conf` can be int or str depending on tesseract version
        conf_raw = data["conf"][i]
        try:
            conf_val = float(conf_raw)
        except (TypeError, ValueError):
            conf_val = -1.0
        if conf_val < 0:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines[key].append(i)
    return lines


def _average_confidence(data: dict[str, Any], indices: list[int]) -> float:
    """Mean Tesseract confidence (0..1) for the words in a row."""
    confs: list[float] = []
    for i in indices:
        try:
            confs.append(float(data["conf"][i]))
        except (TypeError, ValueError):
            continue
    if not confs:
        return 0.0
    return min(1.0, max(0.0, sum(confs) / len(confs) / 100.0))


def parse_marca_image(png_bytes: bytes) -> list[ParsedMarcaRow]:
    """Parse a press-clipping image and return one row per player found.

    The caller is responsible for matching ``surname_clean`` to a DB
    player_id — that logic already exists in ScrapingService.
    """
    import pytesseract  # type: ignore[import-untyped]

    if not png_bytes:
        return []

    try:
        img_rgb = Image.open(BytesIO(png_bytes)).convert("RGB")
    except Exception:
        logger.exception("parse_marca_image: cannot open image")
        return []

    # Tesseract performs better on a high-contrast grayscale.
    ocr_img = ImageOps.autocontrast(img_rgb.convert("L"))

    try:
        data = pytesseract.image_to_data(
            ocr_img,
            lang="spa",
            output_type=pytesseract.Output.DICT,
        )
    except Exception:
        logger.exception("parse_marca_image: tesseract failed")
        return []

    lines = _group_words_into_rows(data)
    rows: list[ParsedMarcaRow] = []
    for indices in lines.values():
        text = " ".join(data["text"][i] for i in indices).strip()
        if not text:
            continue

        x0 = min(data["left"][i] for i in indices)
        y0 = min(data["top"][i] for i in indices)
        x1 = max(data["left"][i] + data["width"][i] for i in indices)
        y1 = max(data["top"][i] + data["height"][i] for i in indices)

        row_width = x1 - x0
        star_left = x0 + int(row_width * (1 - _STARS_REGION_FRACTION))
        star_bbox = (star_left, y0, min(img_rgb.width, x1 + 30), y1 + 2)
        stars = _count_red_stars_in_bbox(img_rgb, star_bbox)

        surname_clean, is_sub, minute = _parse_row_text(text)
        if not surname_clean:
            # Junk row (no parseable surname). Skip.
            continue

        rows.append(
            ParsedMarcaRow(
                raw_text=text,
                surname_clean=surname_clean,
                stars=stars,
                is_substitute=is_sub,
                minute=minute,
                confidence=_average_confidence(data, indices),
            )
        )
    return rows
