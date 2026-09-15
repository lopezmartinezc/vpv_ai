"""Read one news article for the lineup chat — from the two sources only.

The model hands over a URL, so this is the one place where it could make the
server fetch something. It is fenced in accordingly:

* https only, on a closed list of hosts (futbolfantasy and analiticafantasy);
  no IP addresses, no other ports, no credentials in the URL;
* redirects are followed by hand, at most three, and every hop is checked
  against the same list before it is requested;
* HTML only, read up to a size cap, and returned as plain text, cut short.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup

from src.features.scraping.client import _USER_AGENT

ALLOWED_HOSTS = frozenset(
    {
        "futbolfantasy.com",
        "www.futbolfantasy.com",
        "analiticafantasy.com",
        "www.analiticafantasy.com",
    }
)
MAX_REDIRECTS = 3
MAX_BYTES = 1_500_000
MAX_CHARS = 6000
TIMEOUT_SECONDS = 10.0

_NOISE = (
    "script",
    "style",
    "noscript",
    "nav",
    "header",
    "footer",
    "aside",
    "form",
    "iframe",
    "svg",
)


class NewsUrlError(ValueError):
    """A URL the chat may not read, with the reason in words the model can relay."""


def check_url(url: str) -> str:
    """The URL, normalised, if it may be read; NewsUrlError otherwise."""
    parts = urlsplit((url or "").strip())
    if parts.scheme != "https":
        raise NewsUrlError("Solo se leen enlaces https.")
    if parts.username or parts.password:
        raise NewsUrlError("El enlace no puede llevar usuario ni contraseña.")
    host = (parts.hostname or "").lower().rstrip(".")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise NewsUrlError("No se leen direcciones IP, solo futbolfantasy y analiticafantasy.")
    if host not in ALLOWED_HOSTS:
        raise NewsUrlError("Solo se leen noticias de futbolfantasy.com y analiticafantasy.com.")
    try:
        port = parts.port
    except ValueError as exc:
        raise NewsUrlError("Puerto no valido.") from exc
    if port not in (None, 443):
        raise NewsUrlError("Puerto no valido.")
    return urlunsplit(("https", host, parts.path or "/", parts.query, ""))


def article_text(html: str) -> str:
    """The readable text of a page: the article if there is one, without menus."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(_NOISE):
        tag.decompose()
    root = soup.find("article") or soup.find("main") or soup.body or soup
    lines = [" ".join(line.split()) for line in root.get_text("\n").splitlines()]
    text = "\n".join(line for line in lines if line)
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS].rsplit(" ", 1)[0] + " […]"
    return text or "La pagina no tiene texto legible."


async def read_article(url: str, transport: httpx.AsyncBaseTransport | None = None) -> str:
    """Plain text of the article at ``url``. Raises NewsUrlError if not allowed."""
    current = check_url(url)
    async with httpx.AsyncClient(
        timeout=TIMEOUT_SECONDS,
        headers={"User-Agent": _USER_AGENT},
        follow_redirects=False,
        transport=transport,
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            async with client.stream("GET", current) as response:
                if response.is_redirect:
                    current = check_url(urljoin(current, response.headers.get("location", "")))
                    continue
                response.raise_for_status()
                if "html" not in response.headers.get("content-type", ""):
                    raise NewsUrlError("El enlace no es una pagina de noticia.")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) >= MAX_BYTES:
                        break
                html = bytes(body[:MAX_BYTES]).decode(response.encoding or "utf-8", "replace")
                return article_text(html)
    raise NewsUrlError("Demasiadas redirecciones.")
