"""Parse a Marca press-clipping image and extract per-player ratings.

Marca's cromos have a fairly fixed layout: two columns (one per team)
separated by a vertical gutter, each row with shirt number, surname,
optional minute marker, and red star(s) flush right. Layout example
for one row:

    →  7  Reyna   82'   ★★★

We exploit that layout instead of letting Tesseract guess the page
structure:

1. Crop the image vertically to the *player strip* — between the
   thin black divider under the managers' row and the red horizontal
   bar with the stadium name. Everything outside is decoration.
2. Split the strip in half at the horizontal centre so each half
   contains one team's column.
3. Detect player rows in each half by horizontal density of dark
   pixels (text bands).
4. For every row:
   - Crop the left ~75% of the row and OCR it with PSM 7
     ("single text line") for a precise read of just the surname.
   - Crop the right ~25% and count distinct red blobs.
5. Parse the row's OCR text for surname / substitution arrow / sub
   minute.

Dependencies: pytesseract + system Tesseract with the Spanish
language pack (see docs/MUNDIAL_SCRAPING.md).
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)


# Red-pixel thresholds (HSV-ish but in RGB to avoid the conversion).
# Lowered R_MIN from 140 -> 120 after seeing a real-world cromo whose
# red bar was rendered slightly darker (Marca print can drift between
# ~#B40000 and ~#E00000). G/B stay strict so white doesn't qualify.
_RED_R_MIN = 120
_RED_G_MAX = 110
_RED_B_MAX = 110

# Discard connected components smaller than this (anti-alias noise).
_MIN_STAR_BLOB = 25

# Marca never prints more than 4 stars.
_MAX_STARS = 4

# How much of the row width (right side) is reserved for stars.
_STARS_REGION_FRACTION = 0.25

# Dark-pixel threshold (0..255) used to detect text bands.
_DARK_THRESHOLD = 110

# Each text-row should be at least this tall (in px of the original
# image). Below this the band is probably noise / a thin separator.
_MIN_ROW_HEIGHT = 8

# And at most this many — rules out the giant header (score) being
# treated as one giant row.
_MAX_ROW_HEIGHT = 80

# Min density (fraction of dark pixels in a horizontal scan-line)
# for that line to count as "text". Tuned for Marca's print.
_MIN_DARK_DENSITY = 0.05

# A red bar (SoFi Stadium line) is at least this fraction of the
# image width red. Tuned to leave headroom against the title block's
# small red decorations.
# Lowered to 0.35 after real-world testing: Marca's bar has white
# text "Estadio Azteca   70.492 esp." sprawled across, so the row's
# red density dips toward 40-50% in some cromos.
_RED_BAR_FRACTION = 0.35

# Antialiasing / JPEG artifacts can dip 1-2 rows inside the bar
# below threshold. Tolerate them before declaring the bar's top.
_RED_BAR_MAX_MISS = 2

# A 1-px "red" row could be print noise; require at least this many
# contiguous red rows before treating it as the bar.
_RED_BAR_MIN_HEIGHT = 6

# A horizontal "divider" line (between the manager row and the first
# player row) is at least this fraction of the column width black.
# Has to be much higher than _MIN_DARK_DENSITY so we don't grab
# regular text rows.
_DIVIDER_DENSITY = 0.85

# Divider lines are very thin (1-4 px). The manager row above is
# normal text height (~20 px). We want to find the divider, not a
# text band.
_MAX_DIVIDER_HEIGHT = 5


# Words that NEVER appear in a player row but show up in the bar /
# footer (referee, cards, goals). Dropping rows whose raw text hits
# any of these keeps the stadium block out of `unmatched` even when
# the red-bar detector misses for some reason.
_FOOTER_DENYLIST: frozenset[str] = frozenset(
    (
        "estadio",
        "stadium",
        "esp.",
        "espectadores",
        "arbitro",
        "tarjetas",
        "goles",
        "gol anulado",
        "gol",
    )
)

# A row's raw text containing a number with more than 3 digits is
# almost certainly an attendance figure ("70.492", "44 985"), not a
# shirt number (1-2 digits) and not a sub minute (1-2 digits).
_ATTENDANCE_NUMBER = re.compile(r"\d{4,}")


@dataclass
class ParsedMarcaRow:
    """One player extracted from the cromo image.

    `explicit_marker` is the textual marker found on the right of the
    row when there are no red stars to count. The two values it can
    take come from Marca's print edition:

    - "sc": "s/c" - sin calificar (jugó poco)
    - "dash": Unicode minus sign - jugó mal

    None means no marker was detected, so the row stays "null" (no
    rating) when persisted.
    """

    raw_text: str
    surname_clean: str
    stars: int
    is_substitute: bool
    minute: int | None
    confidence: float
    explicit_marker: str | None = None


# ---------------------------------------------------------------------------
# Pure helpers (no Tesseract)
# ---------------------------------------------------------------------------


def _strip_accents_lower(value: str) -> str:
    """Lowercase + strip diacritics so surnames match the roster keys."""
    normalized = unicodedata.normalize("NFD", value)
    no_marks = "".join(c for c in normalized if not unicodedata.combining(c))
    return no_marks.lower().strip()


def _parse_row_text(text: str) -> tuple[str, bool, int | None]:
    """Pull (surname_clean, is_substitute, minute) out of raw row text.

    Tolerates: leading arrow markers ("→" or "->"), leading dorsal
    numbers, trailing "NN'" substitution minute. Drops star glyphs
    so they don't leak into the surname.
    """
    is_sub = bool(re.search(r"→|->", text))
    clean = re.sub(r"→|->", "", text).strip()

    minute_match = re.search(r"(\d{1,2})'", clean)
    minute = int(minute_match.group(1)) if minute_match else None

    clean = clean.replace("★", " ").replace("*", " ")
    clean = re.sub(r"\d{1,2}'", " ", clean)
    clean = re.sub(r"^\s*\d+\s+", "", clean)
    tokens = [tok for tok in clean.split() if tok]

    surname_raw = tokens[-1] if tokens else ""
    return _strip_accents_lower(surname_raw), is_sub, minute


def _count_red_stars_in_bbox(
    img_rgb: Image.Image,
    bbox: tuple[int, int, int, int],
) -> int:
    """Count distinct red blobs inside *bbox* of *img_rgb*.

    Flood-fills 4-neighbourhood connected components of "red enough"
    pixels and returns those above _MIN_STAR_BLOB area.
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


def _detect_text_rows(gray_img: Image.Image) -> list[tuple[int, int]]:
    """Find horizontal bands that probably contain text.

    Heuristic: count dark pixels per scan-line; a contiguous run where
    the density is above _MIN_DARK_DENSITY is a row. Filter by
    height to drop both micro-noise and the big title block.
    """
    pixels = gray_img.load()
    if pixels is None:
        return []
    w, h = gray_img.size
    if w == 0 or h == 0:
        return []

    dark_counts: list[int] = []
    for y in range(h):
        cnt = 0
        for x in range(w):
            v = pixels[x, y]
            if isinstance(v, tuple):
                v = v[0]
            if v < _DARK_THRESHOLD:
                cnt += 1
        dark_counts.append(cnt)

    bands: list[tuple[int, int]] = []
    in_band = False
    band_start = 0
    threshold_px = max(2, int(w * _MIN_DARK_DENSITY))
    for y, cnt in enumerate(dark_counts):
        if cnt >= threshold_px:
            if not in_band:
                band_start = y
                in_band = True
        elif in_band:
            band_end = y
            band_h = band_end - band_start
            if _MIN_ROW_HEIGHT <= band_h <= _MAX_ROW_HEIGHT:
                bands.append((band_start, band_end))
            in_band = False
    if in_band:
        band_end = h
        if _MIN_ROW_HEIGHT <= band_end - band_start <= _MAX_ROW_HEIGHT:
            bands.append((band_start, band_end))
    return bands


def _split_columns(img_rgb: Image.Image) -> tuple[Image.Image, Image.Image]:
    """Halve the image vertically. The split point is fixed at the
    midpoint since Marca cromos are very symmetric."""
    w, h = img_rgb.size
    mid = w // 2
    left = img_rgb.crop((0, 0, mid, h))
    right = img_rgb.crop((mid, 0, w, h))
    return left, right


def _find_red_bar_top_y(img_rgb: Image.Image) -> int | None:
    """Return the y-coordinate of the TOP of the red SoFi-Stadium bar.

    Scans the image bottom-up looking for a contiguous block of
    "mostly red" scan-lines (>= _RED_BAR_FRACTION). Tolerates up to
    _RED_BAR_MAX_MISS rows of dip (antialiasing / JPEG) and demands
    at least _RED_BAR_MIN_HEIGHT rows of red before treating the block
    as the bar. Returns None if no such bar exists.
    """
    pixels = img_rgb.load()
    if pixels is None:
        return None
    w, h = img_rgb.size
    if w == 0 or h == 0:
        return None
    threshold_px = int(w * _RED_BAR_FRACTION)

    in_bar = False
    bar_top: int | None = None
    bar_bottom: int | None = None
    miss_streak = 0

    for y in range(h - 1, -1, -1):
        cnt = 0
        for x in range(w):
            pixel = pixels[x, y]
            if not isinstance(pixel, tuple) or len(pixel) < 3:
                continue
            r, g, b = pixel[0], pixel[1], pixel[2]
            if r >= _RED_R_MIN and g <= _RED_G_MAX and b <= _RED_B_MAX:
                cnt += 1

        if cnt >= threshold_px:
            if not in_bar:
                bar_bottom = y
                in_bar = True
            bar_top = y
            miss_streak = 0
        elif in_bar:
            miss_streak += 1
            if miss_streak > _RED_BAR_MAX_MISS:
                if (
                    bar_bottom is not None
                    and bar_top is not None
                    and (bar_bottom - bar_top + 1) >= _RED_BAR_MIN_HEIGHT
                ):
                    return bar_top
                # False positive — reset and keep scanning up.
                in_bar = False
                bar_top = None
                bar_bottom = None
                miss_streak = 0

    if (
        in_bar
        and bar_bottom is not None
        and bar_top is not None
        and (bar_bottom - bar_top + 1) >= _RED_BAR_MIN_HEIGHT
    ):
        return bar_top
    return None


def _find_top_divider_y(gray_img: Image.Image) -> int | None:
    """Return the y-coordinate just BELOW the thin black divider
    between the managers' row and the first player row.

    A divider has ~85%+ of its scan-line dark, lasts only 1-4 px
    (much thinner than a text row). Returns None if no such line is
    found in the upper third of the image.
    """
    pixels = gray_img.load()
    if pixels is None:
        return None
    w, h = gray_img.size
    if w == 0 or h == 0:
        return None
    threshold_px = int(w * _DIVIDER_DENSITY)
    # We only look in the upper third — past that we'd start finding
    # the divider that sometimes separates the player block from the
    # red bar.
    upper_limit = h // 3

    in_dense = False
    dense_start = 0
    for y in range(upper_limit):
        cnt = 0
        for x in range(w):
            v = pixels[x, y]
            if isinstance(v, tuple):
                v = v[0]
            if v < _DARK_THRESHOLD:
                cnt += 1
        if cnt >= threshold_px:
            if not in_dense:
                dense_start = y
                in_dense = True
        elif in_dense:
            band_height = y - dense_start
            if band_height <= _MAX_DIVIDER_HEIGHT:
                # Skip past the divider so the player row below isn't
                # clipped.
                return y
            in_dense = False
    return None


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def _detect_right_marker(img_rgb: Image.Image) -> str | None:
    """OCR the right portion of a row and detect the rating marker.

    Used as a fallback when no red stars were counted: the row could
    still carry an explicit textual marker like:

    - ``s/c`` (red text, italic) - sin calificar
    - A unicode minus / hyphen / em-dash (black or red) - jugó mal

    Returns ``"sc"``, ``"dash"`` or ``None``.

    A char whitelist + PSM 7 keeps Tesseract from inventing letters
    when the cell is empty.
    """
    import pytesseract

    if img_rgb.width == 0 or img_rgb.height == 0:
        return None

    # 2x upscale + autocontrast — the marker glyphs are tiny.
    upsampled = img_rgb.resize(
        (img_rgb.width * 2, img_rgb.height * 2),
        Image.Resampling.LANCZOS,
    )
    gray = ImageOps.autocontrast(upsampled.convert("L"))

    try:
        text = pytesseract.image_to_string(
            gray,
            # Whitelist: letters s/c (both cases), slash, hyphen,
            # em-dash, unicode minus. These are the only chars Marca
            # uses in the marker column. noqa suppresses the
            # ambiguous-character lint — the unicode glyphs are
            # intentional.
            config="--psm 7 -c tessedit_char_whitelist=sScC/-—−",  # noqa: RUF001
        )
    except Exception:
        logger.exception("_detect_right_marker: tesseract failed")
        return None

    cleaned = (text or "").lower().strip()
    if not cleaned:
        return None
    # The whitelist may leave stray "s" or "c" alone when Tesseract
    # mis-reads noise; only accept the unambiguous combinations.
    if "s/c" in cleaned or "sc" in cleaned:
        return "sc"
    if any(ch in cleaned for ch in ("-", "—", "−")):  # noqa: RUF001
        return "dash"
    return None


def _ocr_single_line(img: Image.Image, lang: str = "spa") -> tuple[str, float]:
    """Run Tesseract on a single-line crop. Returns ``(text, confidence)``."""
    import pytesseract

    # PSM 7 = "Treat the image as a single text line" — much higher
    # accuracy than PSM 6 / 3 on a single-line crop.
    try:
        data = pytesseract.image_to_data(
            img, lang=lang, config="--psm 7", output_type=pytesseract.Output.DICT
        )
    except Exception:
        logger.exception("_ocr_single_line: tesseract failed")
        return "", 0.0

    tokens: list[str] = []
    confs: list[float] = []
    for i, tok in enumerate(data.get("text", []) or []):
        tok_clean = (tok or "").strip()
        if not tok_clean:
            continue
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1.0
        if conf < 0:
            continue
        tokens.append(tok_clean)
        confs.append(conf)
    text = " ".join(tokens).strip()
    confidence = (sum(confs) / len(confs) / 100.0) if confs else 0.0
    return text, max(0.0, min(1.0, confidence))


def _process_column(column_rgb: Image.Image) -> list[ParsedMarcaRow]:
    """Detect rows in one team's column and OCR each one."""
    if column_rgb.width == 0 or column_rgb.height == 0:
        return []

    # 2x upscale + autocontrast — same trick as before, but applied
    # per-line later. We detect rows on the GRAYSCALE original.
    gray = column_rgb.convert("L")
    bands = _detect_text_rows(gray)
    if not bands:
        return []

    rows: list[ParsedMarcaRow] = []
    for y0, y1 in bands:
        # Crop the band a couple of pixels wider so descenders fit.
        crop_y0 = max(0, y0 - 1)
        crop_y1 = min(column_rgb.height, y1 + 2)
        full_row = column_rgb.crop((0, crop_y0, column_rgb.width, crop_y1))

        # Stars region: the right slice.
        star_x0 = int(column_rgb.width * (1 - _STARS_REGION_FRACTION))
        stars = _count_red_stars_in_bbox(
            column_rgb,
            (star_x0, crop_y0, column_rgb.width, crop_y1),
        )

        # When no stars were counted, the row might still have an
        # explicit textual marker (s/c or a dash). Tesseract on the
        # right strip with a char whitelist is reliable enough.
        explicit_marker: str | None = None
        if stars == 0:
            marker_crop = column_rgb.crop((star_x0, crop_y0, column_rgb.width, crop_y1))
            explicit_marker = _detect_right_marker(marker_crop)

        # OCR the LEFT slice (the text part) at 2x scale.
        text_crop = full_row.crop((0, 0, star_x0, full_row.height))
        if text_crop.width == 0 or text_crop.height == 0:
            continue
        text_upsampled = text_crop.resize(
            (text_crop.width * 2, text_crop.height * 2),
            Image.Resampling.LANCZOS,
        )
        text_for_ocr = ImageOps.autocontrast(text_upsampled.convert("L"))
        text, conf = _ocr_single_line(text_for_ocr)
        if not text:
            continue

        # Footer / stadium guard: a row whose text contains a footer
        # keyword or an attendance-like number (4+ digits) is decoration
        # leaking through, not a player. Drop it.
        # Accent-folded comparison so "Árbitro" / "Árbitro" both match.
        text_normalized = _strip_accents_lower(text)
        if any(kw in text_normalized for kw in _FOOTER_DENYLIST):
            continue
        if _ATTENDANCE_NUMBER.search(text):
            continue

        surname_clean, is_sub, minute = _parse_row_text(text)
        if not surname_clean:
            continue

        rows.append(
            ParsedMarcaRow(
                raw_text=text,
                surname_clean=surname_clean,
                stars=stars,
                is_substitute=is_sub,
                minute=minute,
                confidence=conf,
                explicit_marker=explicit_marker,
            )
        )
    return rows


def parse_marca_image(png_bytes: bytes) -> list[ParsedMarcaRow]:
    """Parse a press-clipping image and return one row per player found.

    Uses Marca's static layout (two columns separated at the centre)
    to segment the image *before* OCR. Each detected text band is
    OCR'd individually with PSM 7 for higher accuracy.
    """
    if not png_bytes:
        return []

    try:
        img_rgb = Image.open(BytesIO(png_bytes)).convert("RGB")
    except Exception:
        logger.exception("parse_marca_image: cannot open image")
        return []

    # Crop to the player strip — between the thin black divider that
    # sits under the managers' subtitle and the red horizontal bar
    # with the stadium name. Everything outside is decoration we
    # don't want OCR'd (title, referee, cards, goals).
    gray = img_rgb.convert("L")
    strip_top = _find_top_divider_y(gray) or 0
    strip_bottom = _find_red_bar_top_y(img_rgb) or img_rgb.height
    if strip_bottom <= strip_top:
        # Defensive: a missing divider plus a missing bar means we
        # fall back to the full image.
        strip_top, strip_bottom = 0, img_rgb.height
    logger.debug(
        "parse_marca_image: cropping to y=[%d, %d] (image h=%d)",
        strip_top,
        strip_bottom,
        img_rgb.height,
    )
    strip = img_rgb.crop((0, strip_top, img_rgb.width, strip_bottom))

    left, right = _split_columns(strip)
    rows: list[ParsedMarcaRow] = []
    rows.extend(_process_column(left))
    rows.extend(_process_column(right))
    return rows
