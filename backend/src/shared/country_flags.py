"""Map a team name (as scraped) to its flag emoji.

Used by Telegram messages for tournament draft picks. Mirrors the frontend
mapping at ``frontend/src/lib/country-flags.ts`` — keep both in sync.
"""

from __future__ import annotations

import unicodedata

# Black flag + tag sequences for UK subdivisions (England, Scotland, Wales).
# Built with U+1F3F4 (waving black flag) + tag chars for the ISO 3166-2 code,
# terminated by U+E007F. Telegram and modern OSes render them as the proper
# regional flag.
_UK_SUBDIVISION_EMOJI: dict[str, str] = {
    "gb-eng": "\U0001f3f4\U000e0067\U000e0062\U000e0065\U000e006e\U000e0067\U000e007f",
    "gb-sct": "\U0001f3f4\U000e0067\U000e0062\U000e0073\U000e0063\U000e0074\U000e007f",
    "gb-wls": "\U0001f3f4\U000e0067\U000e0062\U000e0077\U000e006c\U000e0073\U000e007f",
}


def _to_emoji(code: str) -> str:
    """Convert an ISO 3166-1 alpha-2 code to a regional indicator flag emoji.

    Example: 'ar' -> '🇦🇷'. Subdivisions of GB (England/Scotland/Wales) use
    the black-flag + tag-sequence emoji. Returns empty string for unknown
    codes; callers decide whether to render a fallback.
    """
    if code in _UK_SUBDIVISION_EMOJI:
        return _UK_SUBDIVISION_EMOJI[code]
    if "-" in code or len(code) != 2:
        return ""
    return "".join(chr(0x1F1E6 + (ord(c) - ord("a"))) for c in code.lower())


_COUNTRY_MAP: dict[str, str] = {
    # Anfitriones
    "estados unidos": "us",
    "eeuu": "us",
    "usa": "us",
    "mexico": "mx",
    "canada": "ca",
    # CONMEBOL
    "argentina": "ar",
    "brasil": "br",
    "uruguay": "uy",
    "colombia": "co",
    "ecuador": "ec",
    "paraguay": "py",
    "bolivia": "bo",
    "peru": "pe",
    "chile": "cl",
    "venezuela": "ve",
    # UEFA
    "alemania": "de",
    "francia": "fr",
    "espana": "es",
    "portugal": "pt",
    "holanda": "nl",
    "paises bajos": "nl",
    "belgica": "be",
    "italia": "it",
    "inglaterra": "gb-eng",
    "escocia": "gb-sct",
    "gales": "gb-wls",
    "reino unido": "gb",
    "uk": "gb",
    "gran bretana": "gb",
    "irlanda del norte": "gb",
    "suiza": "ch",
    "croacia": "hr",
    "polonia": "pl",
    "austria": "at",
    "noruega": "no",
    "suecia": "se",
    "dinamarca": "dk",
    "finlandia": "fi",
    "islandia": "is",
    "republica checa": "cz",
    "rep checa": "cz",
    "chequia": "cz",
    "eslovaquia": "sk",
    "eslovenia": "si",
    "hungria": "hu",
    "rumania": "ro",
    "bulgaria": "bg",
    "grecia": "gr",
    "turquia": "tr",
    "serbia": "rs",
    "ucrania": "ua",
    "rusia": "ru",
    "irlanda": "ie",
    "bosnia": "ba",
    "bosnia y herzegovina": "ba",
    "bosnia herzegovina": "ba",
    "albania": "al",
    "macedonia del norte": "mk",
    "georgia": "ge",
    "armenia": "am",
    "azerbaiyan": "az",
    "kazajistan": "kz",
    # AFC
    "japon": "jp",
    "corea del sur": "kr",
    "corea": "kr",
    "iran": "ir",
    "iraq": "iq",
    "australia": "au",
    "arabia saudi": "sa",
    "arabia saudita": "sa",
    "uzbekistan": "uz",
    "jordania": "jo",
    "qatar": "qa",
    "catar": "qa",
    "emiratos arabes unidos": "ae",
    "kuwait": "kw",
    "siria": "sy",
    "tailandia": "th",
    "vietnam": "vn",
    "indonesia": "id",
    "malasia": "my",
    "filipinas": "ph",
    "india": "in",
    "china": "cn",
    # CONCACAF
    "panama": "pa",
    "curazao": "cw",
    "haiti": "ht",
    "costa rica": "cr",
    "honduras": "hn",
    "jamaica": "jm",
    "el salvador": "sv",
    "guatemala": "gt",
    "trinidad y tobago": "tt",
    # OFC
    "nueva zelanda": "nz",
    # CAF
    "marruecos": "ma",
    "tunez": "tn",
    "egipto": "eg",
    "ghana": "gh",
    "senegal": "sn",
    "costa de marfil": "ci",
    "sudafrica": "za",
    "argelia": "dz",
    "cabo verde": "cv",
    "nigeria": "ng",
    "camerun": "cm",
    "mali": "ml",
    "burkina faso": "bf",
    "rd congo": "cd",
    "republica democratica del congo": "cd",
    "rep dem congo": "cd",
    "rdc": "cd",
    "rep del congo": "cg",
    "republica del congo": "cg",
    "congo brazzaville": "cg",
    "congo": "cg",
    "zambia": "zm",
    "angola": "ao",
    "kenya": "ke",
    "kenia": "ke",
    "guinea": "gn",
    "uganda": "ug",
    "etiopia": "et",
}


def _normalize(value: str) -> str:
    nfd = unicodedata.normalize("NFD", value)
    stripped = "".join(c for c in nfd if not unicodedata.combining(c))
    out = stripped.lower()
    for ch in (".", "_"):
        out = out.replace(ch, "")
    out = out.replace("-", " ")
    return " ".join(out.split())


def flag_emoji_for(team_name: str | None) -> str:
    """Return the emoji flag for a country team name, or "" if unmapped.

    Returns empty string for clubs (league teams like "Atlético") or unknown
    names. Callers decide whether to render a fallback character.
    """
    if not team_name:
        return ""
    iso = _COUNTRY_MAP.get(_normalize(team_name))
    if not iso:
        return ""
    return _to_emoji(iso)
