"""Parser for live match events from futbolfantasy.com match pages.

Extracts goal, assist, card, and substitution events from the
``div.comentario`` elements in the live commentary section.
"""

from __future__ import annotations

from dataclasses import dataclass

from bs4 import BeautifulSoup

# Map icon filenames to event types.  Extensible — add new icons here
# as they are discovered on futbolfantasy.com.
ICON_MAP: dict[str, str] = {
    "balon.png": "goal",
    "bota.png": "assist",
    "apercibido_box_min.png": "yellow",
    "sancionadoR_box_min.png": "red",
    "icono_entra.png": "sub_in",
    "icono_sale.png": "sub_out",
    "penalti_cometido.png": "penalty_committed",
    "tiro_palo.png": "woodwork",
    "error_garrafal.png": "error_garrafal",
    "balon_robado_ultimo_hombre.png": "last_man_tackle",
}

EVENT_EMOJI: dict[str, str] = {
    "goal": "\u26bd",  # ⚽
    "assist": "\U0001f45f",  # 👟
    "yellow": "\U0001f7e8",  # 🟨
    "red": "\U0001f7e5",  # 🟥
    "sub_in": "\U0001f53c",  # 🔼
    "sub_out": "\U0001f53d",  # 🔽
    "penalty_committed": "\u26a0\ufe0f",  # ⚠️
    "woodwork": "\U0001fab5",  # 🪵
    "error_garrafal": "\U0001f4a5",  # 💥
    "last_man_tackle": "\U0001f6e1\ufe0f",  # 🛡️
}

EVENT_LABEL: dict[str, str] = {
    "goal": "GOL",
    "assist": "ASISTENCIA",
    "yellow": "AMARILLA",
    "red": "ROJA",
    "sub_in": "ENTRA",
    "sub_out": "SALE",
    "penalty_committed": "PENALTI COMETIDO",
    "woodwork": "PALO",
    "error_garrafal": "ERROR GARRAFAL",
    "last_man_tackle": "ROBO ULTIMO HOMBRE",
}


@dataclass(frozen=True)
class LiveEvent:
    """A single parsed event from live match commentary."""

    minute: str
    event_type: str
    player_name: str
    player_slug: str
    raw_text: str

    @property
    def dedup_key(self) -> tuple[str, str, str]:
        """Key for deduplication: (minute, event_type, player_slug)."""
        return (self.minute, self.event_type, self.player_slug)


def parse_live_events(html: str) -> list[LiveEvent]:
    """Extract relevant events from a futbolfantasy.com match page.

    Only returns events that have a known icon (in ICON_MAP) AND
    a linked player (``a.player``).
    """
    soup = BeautifulSoup(html, "lxml")
    events: list[LiveEvent] = []

    for comment in soup.find_all("div", class_="comentario"):
        # Must have at least one icon image
        imgs = comment.find_all("img")
        if not imgs:
            continue

        # Identify event type from icon
        event_type: str | None = None
        for img in imgs:
            src = str(img.get("src", ""))
            filename = src.rsplit("/", 1)[-1] if "/" in src else src
            if filename in ICON_MAP:
                event_type = ICON_MAP[filename]
                break

        if event_type is None:
            continue

        # Extract player link
        player_link = comment.find("a", class_="player")
        if player_link is None:
            continue

        player_name = player_link.get_text(strip=True)
        href = str(player_link.get("href", ""))
        # href shapes seen in production:
        #   .../jugadores/ronald-araujo
        #   .../jugadores/granit-xhaka/world-cup-2026   <- tournament URLs
        #     append the season slug; a naive rsplit("/") here pulled
        #     "world-cup-2026" and nothing matched players.slug, so
        #     the alert went out without "Propietario: ...".
        import re as _re

        m = _re.search(r"/jugadores/([a-z0-9-]+)(?:/|$)", href)
        player_slug = m.group(1) if m else ""
        if not player_slug:
            continue

        # Extract minute
        minute_span = comment.find("span", class_="minutos")
        minute = minute_span.get_text(strip=True) if minute_span else "?"

        # Clean up minute (remove trailing dash, colon suffixes)
        minute = minute.rstrip("-").strip()

        raw_text = comment.get_text(strip=True)[:200]

        events.append(
            LiveEvent(
                minute=minute,
                event_type=event_type,
                player_name=player_name,
                player_slug=player_slug,
                raw_text=raw_text,
            )
        )

    return events
