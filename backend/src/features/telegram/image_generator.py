"""Generate lineup images using Pillow.

Port of the PHP ``createPhoto()`` function from ``claude_data/telegram/telegram_api.php``.
Renders 11 players on a football pitch background with their photos and names.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).resolve().parents[3] / "static"
_TELEGRAM_DIR = _STATIC_DIR / "telegram"
_PLAYERS_DIR = _STATIC_DIR / "players"
_FIELD_IMAGE = _TELEGRAM_DIR / "field5.png"
_FONT_MEDIUM = _TELEGRAM_DIR / "Roboto-Medium.ttf"
_FONT_BOLD = _TELEGRAM_DIR / "Roboto-Bold.ttf"

# Player icon size (px) — same as PHP original
_ICON_SIZE = 260

# Title font size
_TITLE_SIZE = 60

# Player name font size
_NAME_SIZE = 50

# Position coordinates per formation — direct port from PHP $pos_map.
# Keys are formation strings, values map position -> list of (x, y) coords.
POSITION_MAP: dict[str, dict[str, list[tuple[int, int]]]] = {
    "1-3-4-3": {
        "POR": [(780, 1325)],
        "DEF": [(173, 1000), (779, 1000), (1385, 1000)],
        "MED": [(97, 550), (552, 630), (1007, 630), (1462, 550)],
        "DEL": [(173, 180), (779, 180), (1385, 180)],
    },
    "1-3-5-2": {
        "POR": [(780, 1325)],
        "DEF": [(173, 1000), (779, 1000), (1385, 1000)],
        "MED": [(52, 500), (416, 570), (780, 650), (1144, 570), (1508, 500)],
        "DEL": [(325, 180), (1235, 180)],
    },
    "1-4-3-3": {
        "POR": [(780, 1325)],
        "DEF": [(97, 1000), (552, 1000), (1007, 1000), (1462, 1000)],
        "MED": [(173, 550), (779, 550), (1385, 550)],
        "DEL": [(173, 180), (779, 180), (1385, 180)],
    },
    "1-4-4-2": {
        "POR": [(780, 1325)],
        "DEF": [(97, 1000), (552, 1000), (1007, 1000), (1462, 1000)],
        "MED": [(97, 550), (552, 630), (1007, 630), (1462, 550)],
        "DEL": [(325, 180), (1235, 180)],
    },
    "1-4-5-1": {
        "POR": [(780, 1325)],
        "DEF": [(97, 1000), (552, 1000), (1007, 1000), (1462, 1000)],
        "MED": [(52, 500), (416, 570), (780, 650), (1144, 570), (1508, 500)],
        "DEL": [(780, 180)],
    },
    "1-5-3-2": {
        "POR": [(780, 1325)],
        "DEF": [(52, 870), (416, 920), (780, 1000), (1144, 920), (1508, 870)],
        "MED": [(173, 520), (779, 520), (1385, 520)],
        "DEL": [(325, 180), (1235, 180)],
    },
    "1-5-4-1": {
        "POR": [(780, 1325)],
        "DEF": [(52, 870), (416, 920), (780, 1000), (1144, 920), (1508, 870)],
        "MED": [(97, 520), (552, 520), (1007, 520), (1462, 520)],
        "DEL": [(780, 180)],
    },
}


def _load_player_photo(photo_path: str | None) -> Image.Image | None:
    """Load a player photo from the static directory."""
    if not photo_path:
        return None
    full_path = _STATIC_DIR / photo_path
    if not full_path.exists():
        return None
    try:
        img = Image.open(full_path).convert("RGBA")
        return img.resize((_ICON_SIZE, _ICON_SIZE), Image.Resampling.LANCZOS)
    except Exception:
        logger.warning("Failed to load player photo: %s", full_path)
        return None


def _create_placeholder(name: str) -> Image.Image:
    """Create a simple circular placeholder with initials."""
    img = Image.new("RGBA", (_ICON_SIZE, _ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Draw circle
    draw.ellipse([10, 10, _ICON_SIZE - 10, _ICON_SIZE - 10], fill=(60, 60, 60, 200))
    # Draw initials
    initials = "".join(word[0].upper() for word in name.split()[:2] if word)
    try:
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont = ImageFont.truetype(
            str(_FONT_BOLD), 80
        )
    except OSError:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), initials, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (_ICON_SIZE - tw) // 2
    y = (_ICON_SIZE - th) // 2
    draw.text((x, y), initials, fill=(255, 255, 255, 255), font=font)
    return img


def generate_lineup_image(
    display_name: str,
    matchday_number: int,
    formation: str,
    players: list[dict],
) -> bytes:
    """Generate a lineup image and return PNG bytes.

    Parameters
    ----------
    display_name:
        User's display name (e.g. "Carlos").
    matchday_number:
        Matchday number (e.g. 25).
    formation:
        Formation string (e.g. "1-4-3-3").
    players:
        List of dicts with keys: ``position_slot``, ``player_name``, ``photo_path``.
        Must be in ``display_order`` order.
    """
    if formation not in POSITION_MAP:
        raise ValueError(f"Unknown formation: {formation}")

    # Load base field image
    field = Image.open(_FIELD_IMAGE).convert("RGBA")

    # Load fonts
    try:
        font_title: ImageFont.FreeTypeFont | ImageFont.ImageFont = ImageFont.truetype(
            str(_FONT_MEDIUM), _TITLE_SIZE
        )
        font_name: ImageFont.FreeTypeFont | ImageFont.ImageFont = ImageFont.truetype(
            str(_FONT_BOLD), _NAME_SIZE
        )
    except OSError:
        font_title = ImageFont.load_default()
        font_name = ImageFont.load_default()

    draw = ImageDraw.Draw(field)

    # Draw title centered at top
    title = f"{display_name} - Jornada {matchday_number}"
    bbox = draw.textbbox((0, 0), title, font=font_title)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    field_w = field.width
    x = (field_w - tw) // 2
    # Title area is ~84px tall from PHP original
    y = (84 - th) // 2
    draw.text((x, y), title, fill=(0, 0, 0), font=font_title)

    # Place players by position
    pos_coords = POSITION_MAP[formation]
    pos_counters: dict[str, int] = {"POR": 0, "DEF": 0, "MED": 0, "DEL": 0}

    for player in players:
        pos = player["position_slot"]
        idx = pos_counters.get(pos, 0)
        coords = pos_coords.get(pos, [])

        if idx >= len(coords):
            logger.warning("No coords for position %s index %d", pos, idx)
            continue

        px, py = coords[idx]
        pos_counters[pos] = idx + 1

        # Load or create placeholder photo
        photo = _load_player_photo(player.get("photo_path"))
        if photo is None:
            photo = _create_placeholder(player.get("player_name", "?"))

        # Paste photo
        field.paste(photo, (px, py), photo)

        # Draw player name below photo
        name = player.get("player_name", "").strip()
        name_bbox = draw.textbbox((0, 0), name, font=font_name)
        nw = name_bbox[2] - name_bbox[0]
        name_x = px + (_ICON_SIZE // 2) - (nw // 2)
        name_y = py + _ICON_SIZE
        draw.text((name_x, name_y), name, fill=(0, 0, 0), font=font_name)

    # Convert to PNG bytes
    buf = io.BytesIO()
    field.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()
