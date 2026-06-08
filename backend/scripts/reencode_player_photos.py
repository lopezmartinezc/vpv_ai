"""Re-encode existing player WebP photos to drop transparency.

futbolfantasy serves player headshots as PNGs with a transparent
background. Until 2026-06-08 the photo downloader saved the WebPs
keeping that alpha channel, which Telegram's dark theme renders as
black bands on the sides of the picture. This script walks every
.webp under ``static/players/`` and rewrites it with the alpha
flattened onto solid white, matching the new downloader behaviour
without forcing a re-fetch from futbolfantasy.

Usage::

    cd backend
    python -m scripts.reencode_player_photos              # dry-run
    python -m scripts.reencode_player_photos --apply      # apply
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from PIL import Image

logger = logging.getLogger("reencode_player_photos")

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_PHOTOS_DIR = _BACKEND_ROOT / "static" / "players"
_WEBP_QUALITY = 85


def reencode(path: Path) -> str:
    """Return one of: 'rewrote', 'opaque', 'error'."""
    try:
        img = Image.open(path)
    except Exception as exc:
        logger.warning("could not open %s: %s", path.name, exc)
        return "error"

    has_alpha = img.mode in ("RGBA", "LA", "P") and (
        "A" in img.getbands() or (img.mode == "P" and "transparency" in img.info)
    )
    if not has_alpha:
        return "opaque"

    rgba = img.convert("RGBA")
    bg = Image.new("RGB", rgba.size, (255, 255, 255))
    bg.paste(rgba, mask=rgba.split()[-1])
    bg.save(path, format="WEBP", quality=_WEBP_QUALITY)
    return "rewrote"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually rewrite files; otherwise reports counts only.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if not _PHOTOS_DIR.exists():
        logger.error("photos dir not found: %s", _PHOTOS_DIR)
        sys.exit(1)

    files = sorted(_PHOTOS_DIR.glob("*.webp"))
    logger.info("found %d player photos", len(files))

    counts = {"rewrote": 0, "opaque": 0, "error": 0}
    for f in files:
        if not args.apply:
            try:
                img = Image.open(f)
                has_alpha = img.mode in ("RGBA", "LA", "P")
            except Exception:
                has_alpha = False
            counts["rewrote" if has_alpha else "opaque"] += 1
            continue
        result = reencode(f)
        counts[result] += 1

    label = "would rewrite" if not args.apply else "rewrote"
    logger.info(
        "%s=%d  already-opaque=%d  errors=%d",
        label,
        counts["rewrote"],
        counts["opaque"],
        counts["error"],
    )
    if not args.apply:
        logger.info("dry-run; pass --apply to write changes")


if __name__ == "__main__":
    main()
