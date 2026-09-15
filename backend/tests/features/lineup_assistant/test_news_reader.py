"""The chat reads news from the two sources and from nowhere else."""

from __future__ import annotations

import httpx
import pytest

from src.features.lineup_assistant.news_reader import (
    MAX_CHARS,
    NewsUrlError,
    article_text,
    check_url,
    read_article,
)

ARTICLE = "https://www.futbolfantasy.com/laliga/noticias/151241-previa"
PAGE = (
    "<html><head><script>track()</script><style>p{}</style></head><body>"
    "<nav>Inicio Equipos Jugadores</nav>"
    "<article><h1>Previa Barcelona - Racing</h1><p>Pedri vuelve a la convocatoria.</p>"
    "<aside>Relacionadas</aside></article>"
    "<footer>Aviso legal</footer></body></html>"
)


@pytest.mark.parametrize(
    "url",
    [
        ARTICLE,
        "https://futbolfantasy.com/laliga/noticias/1-a",
        "https://www.analiticafantasy.com/partido/100011989-rayo-vallecano-espanyol",
        "https://WWW.FUTBOLFANTASY.COM:443/laliga/noticias/1-a",
    ],
)
def test_the_two_sources_are_allowed(url: str) -> None:
    assert check_url(url).startswith("https://")


@pytest.mark.parametrize(
    "url",
    [
        "http://www.futbolfantasy.com/laliga/noticias/1-a",
        "https://evil.com/laliga/noticias/1-a",
        "https://futbolfantasy.com.evil.com/x",
        "https://evilfutbolfantasy.com/x",
        "https://user:pw@www.futbolfantasy.com/x",
        "https://127.0.0.1/x",
        "https://[::1]/x",
        "https://10.0.0.5/x",
        "https://www.futbolfantasy.com:8443/x",
        "file:///etc/passwd",
        "javascript:alert(1)",
        "",
    ],
)
def test_anything_else_is_refused(url: str) -> None:
    with pytest.raises(NewsUrlError):
        check_url(url)


def test_the_text_is_the_article_without_scripts_or_menus() -> None:
    text = article_text(PAGE)
    assert "Pedri vuelve a la convocatoria." in text
    assert "Previa Barcelona - Racing" in text
    for noise in ("track()", "Inicio Equipos", "Relacionadas", "Aviso legal"):
        assert noise not in text


def test_a_long_article_is_cut_short() -> None:
    text = article_text("<article>" + "palabra " * 5000 + "</article>")
    assert len(text) <= MAX_CHARS + 4
    assert text.endswith("[…]")


async def test_an_article_is_read() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, html=PAGE)

    text = await read_article(ARTICLE, transport=httpx.MockTransport(handler))
    assert "Pedri vuelve" in text


async def test_a_redirect_is_followed_only_within_the_sources() -> None:
    asked: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        asked.append(str(request.url))
        if request.url.path.endswith("previa"):
            return httpx.Response(301, headers={"location": "/laliga/noticias/151241-previa-2"})
        if request.url.path.endswith("previa-2"):
            return httpx.Response(302, headers={"location": "http://169.254.169.254/latest"})
        return httpx.Response(200, html=PAGE)

    with pytest.raises(NewsUrlError):
        await read_article(ARTICLE, transport=httpx.MockTransport(handler))
    # The internal address was refused before any request went to it.
    assert asked == [ARTICLE, ARTICLE + "-2"]


async def test_endless_redirects_stop() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": str(request.url) + "x"})

    with pytest.raises(NewsUrlError, match="redirecciones"):
        await read_article(ARTICLE, transport=httpx.MockTransport(handler))


async def test_something_that_is_not_a_page_is_refused() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=b"%PDF-1.7", headers={"content-type": "application/pdf"}
        )

    with pytest.raises(NewsUrlError):
        await read_article(ARTICLE, transport=httpx.MockTransport(handler))
