"""parse_roster must not store the shirt number as part of the player name.

futbolfantasy prefixes the shirt number to numbered players ("1. Antonio
Sivera"), which was being stored verbatim as the display name.
"""

from __future__ import annotations

from src.features.scraping.parsers import _strip_shirt_number, parse_roster


def test_strip_shirt_number() -> None:
    assert _strip_shirt_number("1. Antonio Sivera") == "Antonio Sivera"
    assert _strip_shirt_number("25. Wojciech Szczesny") == "Wojciech Szczesny"
    assert _strip_shirt_number("Jesús Owono") == "Jesús Owono"
    # No dot after the digits -> leave untouched (not a shirt-number prefix).
    assert _strip_shirt_number("2Pac Name") == "2Pac Name"
    assert _strip_shirt_number("") == ""


def test_parse_roster_strips_shirt_numbers() -> None:
    html = """
    <span class="nombre">Barcelona</span>
    <a class="jugador" href="/jugadores/joan-garcia">13. Joan Garcia</a>
    <a class="jugador" href="/jugadores/aron">Áron Yaakobishvili</a>
    """
    roster = parse_roster(html)
    by_slug = {p.slug: p.display_name for p in roster}
    assert by_slug["joan-garcia"] == "Joan Garcia"
    assert by_slug["aron"] == "Áron Yaakobishvili"
