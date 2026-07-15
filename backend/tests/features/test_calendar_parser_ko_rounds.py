"""parse_calendar must resolve knockout round labels to matchday numbers.

futbolfantasy labels a knockout fixture with ``"Jornada N"`` only once it
has been PLAYED. While pending, the calendar shows the bracket-round
notation instead — ``"1/16"``, ``"1/8"``, ``"1/4"``, ``"1/2"`` and
``"Final"``. The initial regression: those pending fixtures parsed to
``matchday_number == 0`` and scrape_calendar silently skipped them, so a
half-played KO round (one semi finished, the other pending) never got a
Match row — which also made the current-matchday pointer jump past it.

The mapping counts back from the final matchday:
``Final -> end``, ``1/2 -> end-1``, ``1/4 -> end-2`` … (``end - log2(N)``).
"""

from __future__ import annotations

from src.features.scraping.parsers import parse_calendar

# Two semis (one played -> "Jornada 7", one pending -> "1/2") plus the
# still-pending final ("Final"). Mirrors the real Mundial 2026 calendar,
# whose final sits on matchday 8.
CAL_HTML = """
<section class="lista">
  <a class="partido terminado" href="/partidos/22836-francia-espana">
    <div class="fase">Jornada 7</div>
    <div class="equipo local"><img alt="Francia"></div>
    <div class="equipo visitante"><img alt="España"></div>
    <div class="resultado">0-2</div>
  </a>
  <a class="partido" href="/partidos/22838-inglaterra-argentina">
    <div class="fase">1/2</div>
    <div class="equipo local"><img alt="Inglaterra"></div>
    <div class="equipo visitante"><img alt="Argentina"></div>
    <div class="date">Mié 15/07 21:00h</div>
  </a>
  <a class="partido" href="/partidos/24047-espana-ingarg">
    <div class="fase">Final</div>
    <div class="equipo local"><img alt="España"></div>
    <div class="equipo visitante"><img alt="ING/ARG"></div>
    <div class="date">Dom 19/07 21:00h</div>
  </a>
</section>
"""


def _by_source(matches: list, source_id: int):
    return next(m for m in matches if m.source_id == source_id)


def test_played_ko_fixture_keeps_jornada_number() -> None:
    matches = parse_calendar(CAL_HTML, season_year=2026, knockout_final_matchday=8)
    assert _by_source(matches, 22836).matchday_number == 7


def test_pending_semifinal_label_maps_to_matchday() -> None:
    # "1/2" (semis) -> final(8) - log2(2) = 7
    matches = parse_calendar(CAL_HTML, season_year=2026, knockout_final_matchday=8)
    assert _by_source(matches, 22838).matchday_number == 7


def test_pending_final_label_maps_to_last_matchday() -> None:
    matches = parse_calendar(CAL_HTML, season_year=2026, knockout_final_matchday=8)
    assert _by_source(matches, 24047).matchday_number == 8


def test_all_bracket_fractions_map_back_from_final() -> None:
    html = """
    <section class="lista">
      <a class="partido" href="/partidos/1-a-b">
        <div class="fase">1/16</div>
        <div class="equipo local"><img alt="A"></div>
        <div class="equipo visitante"><img alt="B"></div>
      </a>
      <a class="partido" href="/partidos/2-c-d">
        <div class="fase">1/8</div>
        <div class="equipo local"><img alt="C"></div>
        <div class="equipo visitante"><img alt="D"></div>
      </a>
      <a class="partido" href="/partidos/3-e-f">
        <div class="fase">1/4</div>
        <div class="equipo local"><img alt="E"></div>
        <div class="equipo visitante"><img alt="F"></div>
      </a>
    </section>
    """
    matches = parse_calendar(html, season_year=2026, knockout_final_matchday=8)
    assert _by_source(matches, 1).matchday_number == 4  # 1/16 -> 8-4
    assert _by_source(matches, 2).matchday_number == 5  # 1/8  -> 8-3
    assert _by_source(matches, 3).matchday_number == 6  # 1/4  -> 8-2


def test_ko_labels_ignored_without_final_matchday() -> None:
    # Leagues never pass knockout_final_matchday; a stray non-"Jornada"
    # label must NOT be coerced into a bogus matchday.
    matches = parse_calendar(CAL_HTML, season_year=2026)
    assert _by_source(matches, 22838).matchday_number == 0
    assert _by_source(matches, 24047).matchday_number == 0
