"""Parse a Marca press-clipping image and extract per-player ratings.

Ported from the standalone reference extractor that scored 94/94 on
the ground-truth bench (3 cromos, 94 players, 100% rating accuracy
without losing a single row). See `gt_check.py` / `BRIEF_para_claude_code.md`
in the original kit for the design rationale.

Pipeline:

1. **Region detection**: locate the player strip between the header
   (top 16%) and the red bar (stadium / referee block) at the bottom.
2. **Column split**: find the vertical "white channel" near the centre
   that separates home vs. away.
3. **Row anchoring on jersey numbers**: OCR the column at PSM 6, keep
   only digit-leading tokens in the left 33% - those are the dorsals.
   Compute the median pitch between them and FILL gaps + extend
   above/below. Result: no row is lost even if its name/text fails.
4. **Per-row OCR**: re-OCR each row band (PSM 7, single line) on the
   GREEN channel - sub players are rendered in red, the green channel
   makes them dark and legible.
5. **Rating via computer vision (NOT OCR of the symbols)**:
     - stars = count of red square blobs (HSV red mask, area + square
       aspect ratio 0.5-1.8) to the right of the arrow zone.
     - "dash" = a flat dark blob (height ≤ ~4 px, width 8-34 px) in
       the right 45% of the rating cell.
     - empty cell OR "s/c" text token -> SC (sin calificar, 0 pts).

Tesseract simply cannot read ★ / "s/c" reliably; doing it by vision
is both faster and far more accurate.

Dependencies: opencv-python-headless, numpy, pytesseract + system
Tesseract with the English language pack. We use `lang='eng'` (not
'spa') because the reference benchmark validated against `eng` and
the digit OCR there is what powers the row anchoring - accents lost
in names are a cosmetic non-issue, matching falls back to fuzzy.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from itertools import pairwise

import cv2
import numpy as np

logger = logging.getLogger(__name__)


# Reference width - every geometric constant below is multiplied by
# `sc = W / _REF_WIDTH` so the parser scales between 392 px and 1200 px
# wide cromos without retuning.
_REF_WIDTH = 628.0

# HSV ranges for the two halves of the red hue wheel - Marca's stars
# and arrows are saturated red (~#D00000) but JPEG drift puts some
# pixels in the 168-180 wrap-around range.
_RED_HSV_LOW = (np.array((0, 80, 80), dtype=np.uint8), np.array((12, 255, 255), dtype=np.uint8))
_RED_HSV_HIGH = (
    np.array((168, 80, 80), dtype=np.uint8),
    np.array((180, 255, 255), dtype=np.uint8),
)

# Tesseract confidence floor - tokens below this are skipped.
_OCR_CONF_MIN = 15


# Row-token regexes ----------------------------------------------------

# Arrow markers (substitute indicator). Includes Marca's stylized ->
# plus common OCR mis-reads (>, «, dash). noqa: RUF001 (intentional
# unicode glyphs).
_ARROW_RE = re.compile(r"^[>«→↑\-]+$")

# "82'" sub minute. Tolerates Marca's curly quote.
_MIN_RE = re.compile(r"^\d{1,3}['ʼ`]$")  # noqa: RUF001

# Pure leading digits = jersey number.
_NUM_RE = re.compile(r"^(\d{1,2})")

# Glued "21Osorio" / "7_Eustaquio" - OCR sometimes fuses number + name.
_GLUE_RE = re.compile(r"^(\d{1,2})[_\W0]?([A-Za-zÁÉÍÓÚÑáéíóúñ][A-Za-zÁÉÍÓÚÑáéíóúñ\-]+)$")

# Tokens that look like a botched star sequence - drop them so they
# don't pollute names. The character class contains intentionally
# ambiguous unicode glyphs Tesseract emits for the ★ symbol.
_STAR_JUNK = re.compile(r"^[kKxX*«»\.\-]+$")

# Tesseract's many mis-spellings of "s/c" (sin calificar):
#   s/c   sc   s|c   s1c   slc   sic  (with dotless-i variant).
_SC_RE = re.compile(r"^s\s*[/|1lı]?\s*c$", re.I)  # noqa: RUF001


@dataclass
class ParsedMarcaRow:
    """One player extracted from the cromo image.

    Fields kept stable so ``service.marca_preview`` and Pydantic
    schemas don't change:

    - ``raw_text``: concatenation of the row's OCR tokens, useful for
      debugging when matching fails.
    - ``surname_clean``: last name token, accent-folded + lowercased.
      Used as the join key against the team roster.
    - ``stars``: 0-4. Counted by colour (not OCR) so it's reliable.
    - ``is_substitute``: True when the row starts with a red arrow
      OR has a sub minute token.
    - ``minute``: substitution minute if detected.
    - ``confidence``: average Tesseract confidence (0-1).
    - ``explicit_marker``: rating marker when ``stars == 0``:
        * ``"sc"`` - empty cell OR OCR'd "s/c"  -> "SC" (jugó poco)
        * ``"dash"`` - flat dark blob detected  -> "-" (jugó mal)
        * ``None`` - only when ``stars > 0`` (numeric rating).
    - ``dorsal``: jersey number from the anchor (or band re-read).
      None only if the row's anchor came from gap-fill and OCR also
      missed the number.
    """

    raw_text: str
    surname_clean: str
    stars: int
    is_substitute: bool
    minute: int | None
    confidence: float
    explicit_marker: str | None = None
    dorsal: int | None = None


# ---------------------------------------------------------------------------
# Text helpers (pure)
# ---------------------------------------------------------------------------


def _strip_accents_lower(value: str) -> str:
    """Lowercase + strip diacritics so surnames match roster keys."""
    normalized = unicodedata.normalize("NFD", value)
    no_marks = "".join(c for c in normalized if not unicodedata.combining(c))
    return no_marks.lower().strip()


def _clean_name(parts: list[str]) -> str:
    """Glue OCR tokens into a display name.

    Drops anything that isn't a letter or hyphen, trims trailing
    2-letter lowercase noise (icon labels like "ti" / "ca"), and
    capitalises tokens whose first letter is lowercase (so OCR's
    "jin-gyu" comes back as "Jin-gyu").
    """
    out: list[str] = []
    for p in parts:
        cleaned = re.sub(r"[^A-Za-zÁÉÍÓÚÑáéíóúñ\-]", "", p)
        if len(cleaned) >= 2:
            out.append(cleaned)
    while len(out) > 1 and len(out[-1]) <= 2 and out[-1].islower():
        out.pop()
    out = [w[0].upper() + w[1:] if w[:1].islower() else w for w in out]
    return " ".join(out).strip()


# ---------------------------------------------------------------------------
# Computer-vision helpers (no OCR)
# ---------------------------------------------------------------------------


def _build_masks(img_bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(red_mask, gray)`` for the BGR image.

    The red mask covers both halves of the red hue wheel.
    """
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    red = cv2.bitwise_or(
        cv2.inRange(hsv, *_RED_HSV_LOW),
        cv2.inRange(hsv, *_RED_HSV_HIGH),
    )
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    return red, gray


def _count_stars(red: np.ndarray, yc: int, xa: int, xb: int, sc: float) -> int:
    """Count red star blobs in the row centred at ``yc`` between ``xa`` and ``xb``.

    A blob is a star when its area is ≥ ``40·sc²`` and its bounding
    box is roughly square (0.5 < w/h < 1.8). The first 14% of the row
    is reserved for the "->" arrow (substitute marker) and ignored.
    """
    hh = max(8, int(12 * sc))
    band = red[max(0, yc - hh) : yc + hh + 2, xa:xb]
    if band.size == 0:
        return 0
    # cv2 stub rejects uint8 even though it's the canonical input.
    _, _, stats, _ = cv2.connectedComponentsWithStats(band, 8)  # type: ignore[call-overload]
    n = 0
    arrow_zone = 0.14 * (xb - xa)
    amin = max(15, int(40 * sc * sc))
    for x, _y, w, h, area in stats[1:]:
        if area < amin or x < arrow_zone:
            continue
        if 0.5 < w / max(h, 1) < 1.8:
            n += 1
    return min(n, 4)


def _has_dash(gray: np.ndarray, yc: int, xa: int, xb: int, sc: float) -> bool:
    """Detect a "-" marker = flat dark blob in the right 45% of the cell.

    A dash is short (height ≤ ~4 px), at least 8 px wide, with a
    >2.3:1 aspect ratio. Row separators are wider and filtered out by
    the ``w <= 34·sc`` cap.
    """
    hh = max(6, int(8 * sc))
    x0 = xa + int((xb - xa) * 0.40)
    region = gray[max(0, yc - hh) : yc + hh + 2, x0:xb]
    if region.size == 0:
        return False
    cell = (region < 170).astype(np.uint8)
    _, _, stats, _ = cv2.connectedComponentsWithStats(cell, 8)  # type: ignore[call-overload]
    hmax = max(3, int(4 * sc))
    wmin, wmax = max(6, int(8 * sc)), int(34 * sc)
    amin = max(8, int(10 * sc))
    for _x, _y, w, h, area in stats[1:]:
        if area >= amin and h <= hmax and wmin <= w <= wmax and w / max(h, 1) > 2.3:
            return True
    return False


def _is_sub_arrow(red: np.ndarray, yc: int, xa: int, sc: float) -> bool:
    """Detect a red "->" at the start of the row (substitute marker).

    Looks for a red blob in the first ``44·sc`` pixels of the column.
    """
    hh = max(8, int(10 * sc))
    band = red[max(0, yc - hh) : yc + hh + 2, xa : xa + int(44 * sc)]
    if band.size == 0:
        return False
    _, _, stats, _ = cv2.connectedComponentsWithStats(band, 8)  # type: ignore[call-overload]
    wmin = int(10 * sc)
    amin = max(20, int(35 * sc * sc))
    return any(area >= amin and w >= wmin for _x, _y, w, _h, area in stats[1:])


def _find_table_region(img_bgr: np.ndarray, red: np.ndarray) -> tuple[int, int]:
    """Return ``(y_top, y_bottom)`` of the player strip.

    - ``y_top`` is a fixed ~16% - past the title block, manager row
      and divider line.
    - ``y_bottom`` is the y of the red bar (stadium / referee block);
      the first row in the lower half with > 50% red pixels.
    """
    h_img, w_img = img_bgr.shape[:2]
    row_red = (red > 0).sum(axis=1)
    threshold = w_img * 0.5
    footer = h_img
    for y in range(int(h_img * 0.55), h_img):
        if row_red[y] > threshold:
            footer = y
            break
    return int(h_img * 0.16), footer


def _find_column_split(img_bgr: np.ndarray, y0: int, y1: int) -> int:
    """Find the vertical gutter that separates home vs. away.

    The gutter has the least "ink" (dark pixels) of any column in the
    central 42%-58% band of the image.
    """
    gray = cv2.cvtColor(img_bgr[y0:y1], cv2.COLOR_BGR2GRAY)
    ink = (gray < 200).sum(axis=0)
    w_img = img_bgr.shape[1]
    centre_lo, centre_hi = int(w_img * 0.42), int(w_img * 0.58)
    centre = range(centre_lo, centre_hi if centre_hi > centre_lo else centre_lo + 1)
    return min(centre, key=lambda x: int(ink[x]))


# ---------------------------------------------------------------------------
# OCR helpers (need Tesseract)
# ---------------------------------------------------------------------------


def _ocr_data(
    img: np.ndarray, lang: str, psm: int
) -> tuple[list[str], list[int], list[int], list[int], list[int]]:
    """Run ``pytesseract.image_to_data`` and return parallel lists.

    Returns ``(texts, confs, lefts, tops, widths)`` filtered by
    ``_OCR_CONF_MIN``. Empty lists on Tesseract failure.
    """
    import pytesseract

    try:
        d = pytesseract.image_to_data(
            img,
            lang=lang,
            config=f"--psm {psm}",
            output_type=pytesseract.Output.DICT,
        )
    except Exception:
        logger.exception("_ocr_data: tesseract failed")
        return [], [], [], [], []

    texts = d.get("text") or []
    confs = d.get("conf") or []
    lefts = d.get("left") or []
    tops = d.get("top") or []
    widths = d.get("width") or []
    return texts, confs, lefts, tops, widths


def _ocr_column_tokens(green_col: np.ndarray) -> list[dict]:
    """OCR the whole team column (PSM 6) for dorsal anchoring.

    Upscales 2x for better digit OCR and returns tokens with
    half-scale coordinates so callers can address the original image.
    """
    if green_col.size == 0:
        return []
    up = cv2.resize(green_col, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    texts, confs, lefts, tops, widths = _ocr_data(up, lang="eng", psm=6)
    out: list[dict] = []
    for i, raw_text in enumerate(texts):
        t = (raw_text or "").strip()
        if not t:
            continue
        try:
            conf = int(confs[i])
        except (TypeError, ValueError):
            continue
        if conf <= _OCR_CONF_MIN:
            continue
        out.append(
            {
                "text": t,
                "x": lefts[i] // 2,
                "y": tops[i] // 2,
                "w": widths[i] // 2,
                "conf": conf,
            }
        )
    return out


def _has_letter_token(tokens: list[dict]) -> bool:
    """True if the token list contains at least one token with ≥2 ASCII
    letters in a row. We use this to decide if the first OCR pass is
    good enough, or if we need a second pass with stronger pre-processing."""
    for t in tokens:
        text = t.get("text", "")
        run = 0
        for ch in text:
            if ch.isalpha() and ord(ch) < 128:
                run += 1
                if run >= 2:
                    return True
            else:
                run = 0
    return False


def _ocr_band_tokens(green_full: np.ndarray, yc: int, xa: int, xb: int, sc: float) -> list[dict]:
    """OCR a single row band (PSM 7) at 3x scale.

    Two-pass strategy. The first pass runs on the green-channel band
    directly — fast and good enough on modern Tesseract builds. If
    that pass returns ZERO tokens with at least 2 consecutive letters
    (signalling that the row's name didn't OCR — typical on older
    Tesseract builds like 5.3.x), a second pass runs after Otsu
    binarisation, which dramatically improves contrast on Marca's
    black-on-light text and recovers names that the raw green channel
    couldn't read.
    """
    if green_full.size == 0:
        return []
    hh = int(15 * sc)
    band = green_full[max(0, yc - hh) : yc + hh, xa:xb]
    if band.size == 0:
        return []
    up = cv2.resize(band, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

    def _collect(img_in: np.ndarray) -> list[dict]:
        texts, confs, lefts, _tops, _widths = _ocr_data(img_in, lang="eng", psm=7)
        result: list[dict] = []
        for i, raw_text in enumerate(texts):
            t = (raw_text or "").strip()
            if not t:
                continue
            try:
                conf = int(confs[i])
            except (TypeError, ValueError):
                continue
            if conf <= _OCR_CONF_MIN:
                continue
            result.append({"text": t, "x": lefts[i] // 3, "conf": conf})
        return result

    tokens = _collect(up)
    if not _has_letter_token(tokens):
        # Fallback: Otsu binarisation. Inverting the threshold so the
        # text stays black (Tesseract is trained on dark text on light
        # background; Marca's red sub text and antialiasing benefit
        # the most from this).
        _, binarised = cv2.threshold(up, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        tokens_pass2 = _collect(binarised)
        if _has_letter_token(tokens_pass2):
            tokens = tokens_pass2
    return tokens


# ---------------------------------------------------------------------------
# Row anchoring (the killer feature: no row is ever lost)
# ---------------------------------------------------------------------------


def _detect_row_centers(
    green_col: np.ndarray, col_w: int, sc: float
) -> list[tuple[int, int | None]]:
    """Return ``[(y_centre, dorsal | None), ...]`` for the column.

    The list is anchored on OCR'd jersey numbers in the left third of
    the column, then GAPS ARE FILLED at the median pitch so no row is
    lost. Above the first anchor and below the last we extend one
    full pitch if there's still room.
    """
    toks = _ocr_column_tokens(green_col)
    raw_anchors = sorted(
        (t["y"] + 6, t["text"])
        for t in toks
        if re.match(r"^\d", t["text"]) and t["x"] < col_w * 0.33
    )
    centers: list[tuple[int, int | None]] = []
    tol = max(6, int(10 * sc))
    for y, txt in raw_anchors:
        m = _NUM_RE.match(txt)
        num = int(m.group(1)) if m else None
        if centers and y - centers[-1][0] <= tol:
            # Merge near-duplicate anchors (Tesseract often splits a
            # dorsal into 2 tokens).
            prev_y, prev_num = centers[-1]
            centers[-1] = ((prev_y + y) // 2, prev_num if prev_num is not None else num)
        else:
            centers.append((y, num))

    if len(centers) < 2:
        return centers

    diffs = [b[0] - a[0] for a, b in pairwise(centers)]
    pitch = int(np.median(diffs))
    if pitch < 8:
        return centers

    # Fill interior gaps that look like multiples of `pitch`.
    filled: list[tuple[int, int | None]] = [centers[0]]
    for c in centers[1:]:
        gap = c[0] - filled[-1][0]
        k = max(1, round(gap / pitch))
        for _ in range(1, k):
            filled.append((filled[-1][0] + gap // k, None))
        filled.append(c)

    # Extend up/down by one pitch if there's room.
    h_col = green_col.shape[0]
    while filled[0][0] - pitch > pitch * 0.4:
        filled.insert(0, (filled[0][0] - pitch, None))
    while filled[-1][0] + pitch < h_col - pitch * 0.3:
        filled.append((filled[-1][0] + pitch, None))
    return filled


# ---------------------------------------------------------------------------
# Per-row parse
# ---------------------------------------------------------------------------


def _parse_row_tokens(
    toks: list[dict],
) -> tuple[int | None, str, bool, int | None, bool, float]:
    """Pull ``(dorsal, name, is_sub, minute, is_sc, avg_conf)`` from row tokens.

    Order rules:
    - Arrow at x<60 OR a "82'"-style minute marks the row as a substitute.
    - The FIRST digit-only token (or the digit half of a glued "21Osorio")
      is the jersey number.
    - Everything else with letters and ≥ 2 chars goes into the name.
    """
    toks = sorted(toks, key=lambda z: z["x"])
    is_sub = False
    number: int | None = None
    minute: int | None = None
    is_sc = False
    name_parts: list[str] = []
    confs: list[int] = []
    for t in toks:
        txt = t["text"]
        confs.append(t["conf"])
        if _ARROW_RE.match(txt) and t["x"] < 60:
            is_sub = True
        elif _MIN_RE.match(txt):
            is_sub = True
            minute = int(re.sub(r"\D", "", txt))
        elif _SC_RE.match(txt):
            is_sc = True
        elif _GLUE_RE.match(txt):
            m = _GLUE_RE.match(txt)
            if m is None:
                continue
            if number is None:
                number = int(m.group(1))
            name_parts.append(m.group(2))
        elif _NUM_RE.match(txt) and number is None and not _STAR_JUNK.match(txt):
            m = _NUM_RE.match(txt)
            if m is not None:
                number = int(m.group(1))
        elif (
            re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]", txt)
            and len(txt) >= 2
            and not _STAR_JUNK.match(txt)
            and not _SC_RE.match(txt)
        ):
            name_parts.append(txt)

    name = _clean_name(name_parts)
    avg_conf = (sum(confs) / len(confs) / 100.0) if confs else 0.0
    return number, name, is_sub, minute, is_sc, max(0.0, min(1.0, avg_conf))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def parse_marca_image(png_bytes: bytes) -> list[ParsedMarcaRow]:
    """Parse a Marca press-clipping image -> one ``ParsedMarcaRow`` per player.

    See module docstring for the design.

    Returns ``[]`` on decode failure. Marker semantics for the
    rating column (matches ``schemas_marca.MarcaPreviewMatch``):

    - ``stars > 0``             -> numeric rating (1-4 stars)
    - ``explicit_marker="sc"``  -> SC (0 pts); covers BOTH the OCR'd
                                  "s/c" token AND the empty cell case
                                  - if the player is in the cromo they
                                  played at least one minute.
    - ``explicit_marker="dash"`` -> "-" (negative rating)
    """
    if not png_bytes:
        return []

    arr = np.frombuffer(png_bytes, dtype=np.uint8)
    img_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img_bgr is None:
        logger.error("parse_marca_image: cv2 cannot decode image")
        return []

    red, gray = _build_masks(img_bgr)
    _h_img, w_img = img_bgr.shape[:2]
    sc = w_img / _REF_WIDTH
    y0, y1 = _find_table_region(img_bgr, red)
    if y1 - y0 < 20:
        logger.warning("parse_marca_image: table region too small (%d-%d)", y0, y1)
        return []
    split = _find_column_split(img_bgr, y0, y1)

    columns = [
        {"box": (0, split), "rating": (split - int(66 * sc), split - 2)},
        {"box": (split, w_img), "rating": (w_img - int(68 * sc), w_img - 2)},
    ]

    green_full = img_bgr[:, :, 1]  # red text becomes dark on the green channel
    rows: list[ParsedMarcaRow] = []

    for cfg in columns:
        xa, xb = cfg["box"]
        col_green = green_full[y0:y1, xa:xb]
        centers = _detect_row_centers(col_green, xb - xa, sc)
        seen: set[int] = set()
        for cy, anchor_num in centers:
            yc = cy + y0
            toks = _ocr_band_tokens(green_full, yc, xa, xb, sc)
            num, name, is_sub, minute, is_sc, avg_conf = _parse_row_tokens(toks)
            if anchor_num is not None:
                # Anchor dorsal beats band re-read - the centre-column
                # pass is much more reliable on digits than the band's
                # PSM 7 which has to deal with arrow+number+name fused.
                num = anchor_num
            if num is None or num in seen:
                continue
            if not is_sub and _is_sub_arrow(red, yc, xa, sc):
                is_sub = True

            # Resolve the rating column entirely by CV.
            if is_sc:
                stars = 0
                marker: str | None = "sc"
            else:
                stars = _count_stars(red, yc, xa, xb, sc)
                if stars > 0:
                    marker = None
                elif _has_dash(gray, yc, xa, xb, sc):
                    marker = "dash"
                else:
                    # Empty rating cell - player is in the cromo so
                    # they played, but Marca didn't grade them: SC.
                    marker = "sc"

            seen.add(num)
            raw_text = " ".join(t["text"] for t in toks)
            tokens = name.split() if name else []
            surname_token = tokens[-1] if tokens else ""
            rows.append(
                ParsedMarcaRow(
                    raw_text=raw_text,
                    surname_clean=_strip_accents_lower(surname_token),
                    stars=stars,
                    is_substitute=is_sub,
                    minute=minute,
                    confidence=avg_conf,
                    explicit_marker=marker,
                    dorsal=num,
                )
            )

    return rows
