"""The proposed eleven: valid, without the absent, and not discounted twice."""

from __future__ import annotations

from src.features.lineup_assistant.optimizer import (
    Candidate,
    Formation,
    best_lineup,
    play_probability,
    value_of,
)

FORMATIONS = [
    Formation(name, d, m, f)
    for name, d, m, f in (
        ("1-3-4-3", 3, 4, 3),
        ("1-3-5-2", 3, 5, 2),
        ("1-4-3-3", 4, 3, 3),
        ("1-4-4-2", 4, 4, 2),
        ("1-4-5-1", 4, 5, 1),
        ("1-5-3-2", 5, 3, 2),
        ("1-5-4-1", 5, 4, 1),
    )
]


def c(pid: int, position: str, xpts: float | None, **kw: object) -> Candidate:
    kw.setdefault("starter_pct", 100.0)
    return Candidate(pid, f"P{pid}", position, "Equipo", xpts, **kw)  # type: ignore[arg-type]


def squad(**overrides: Candidate) -> list[Candidate]:
    """2 POR, 6 DEF, 6 MED, 4 DEL; worth less the higher the id within a position."""
    base = (
        [c(1, "POR", 6.0), c(2, "POR", 3.0)]
        + [c(10 + i, "DEF", 5.0 - i * 0.5) for i in range(6)]
        + [c(20 + i, "MED", 5.0 - i * 0.5) for i in range(6)]
        + [c(30 + i, "DEL", 5.0 - i * 0.5) for i in range(4)]
    )
    by_id = {x.player_id: x for x in base}
    for key, cand in overrides.items():
        by_id[int(key[1:])] = cand
    return list(by_id.values())


def counts(eleven: list) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in eleven:
        out[v.candidate.position] = out.get(v.candidate.position, 0) + 1
    return out


def test_the_eleven_is_a_valid_formation() -> None:
    s = best_lineup(squad(), FORMATIONS)
    assert s is not None
    d, m, f = (int(x) for x in s.formation.split("-")[1:])
    assert counts(s.eleven) == {"POR": 1, "DEF": d, "MED": m, "DEL": f}
    assert len(s.eleven) == 11
    assert len(s.bench) == len(squad()) - 11


def test_the_formation_that_adds_most_wins() -> None:
    # Two strong forwards more than any fifth midfielder or fourth defender.
    s = best_lineup(squad(p32=c(32, "DEL", 9.0), p33=c(33, "DEL", 9.0)), FORMATIONS)
    assert s is not None and s.formation.endswith("-3")
    assert {32, 33} <= {v.candidate.player_id for v in s.eleven}


def test_the_injured_and_suspended_are_left_out_whatever_their_forecast() -> None:
    s = best_lineup(
        squad(
            p1=c(
                1,
                "POR",
                9.0,
                statuses=frozenset({"lesionado"}),
                source_probs={"futbolfantasy": 90},
            ),
            p30=c(30, "DEL", 9.0, statuses=frozenset({"sancionado"})),
        ),
        FORMATIONS,
    )
    assert s is not None
    chosen = {v.candidate.player_id for v in s.eleven}
    assert 1 not in chosen and 2 in chosen
    assert 30 not in chosen
    assert value_of(c(1, "POR", 9.0, statuses=frozenset({"no_disponible"}))).value == 0


def test_the_chance_is_the_mean_of_the_sources_and_counted_once() -> None:
    both = c(
        1,
        "MED",
        10.0,
        starter_pct=20.0,
        source_probs={"futbolfantasy": 80, "analiticafantasy": 60},
    )
    prob, basis = play_probability(both)
    assert prob == 0.7
    assert "FF 80 %" in basis and "AF 60 %" in basis
    # xpts_if_plays is before any starter discount: 10 x 0.7, not 10 x 0.2 x 0.7.
    assert value_of(both).value == 7.0
    # A source listing him without a percentage does not drag the mean down.
    one = c(2, "MED", 10.0, source_probs={"futbolfantasy": 50, "analiticafantasy": None})
    assert play_probability(one)[0] == 0.5


def test_each_predicted11_eleven_counts_like_one_more_site() -> None:
    # FF 70, AF 60, and two of the three best predictors put him in.
    picked = c(
        1,
        "MED",
        10.0,
        source_probs={
            "futbolfantasy": 70,
            "analiticafantasy": 60,
            "predicted11_1": 100,
            "predicted11_2": 100,
            "predicted11_3": 0,
        },
    )
    prob, basis = play_probability(picked)
    assert prob == 0.66
    assert basis == "alineaciones probables (AF 60 % · FF 70 % · P11 2/3)"
    assert value_of(picked).value == 6.6
    # Left out by the only predictor with an eleven: that alone says 0.
    assert play_probability(c(2, "MED", 10.0, source_probs={"predicted11_1": 0}))[0] == 0


def test_without_sources_the_history_decides_and_a_doubt_halves_it() -> None:
    assert play_probability(c(1, "DEF", 5.0, starter_pct=80.0))[0] == 0.8
    doubt = c(2, "DEF", 5.0, starter_pct=80.0, statuses=frozenset({"duda"}))
    assert play_probability(doubt)[0] == 0.4
    # With a percentage from a source the doubt is already priced in.
    priced = c(3, "DEF", 5.0, statuses=frozenset({"duda"}), source_probs={"futbolfantasy": 50})
    assert play_probability(priced)[0] == 0.5
    assert play_probability(c(4, "DEF", 5.0, starter_pct=None))[0] == 0


def test_no_match_or_no_forecast_is_worth_nothing_and_says_which() -> None:
    idle = value_of(c(1, "DEL", 5.0, has_match=False))
    assert (idle.value, idle.basis) == (0.0, "sin partido esta jornada")
    unknown = value_of(c(2, "DEL", None))
    assert (unknown.value, unknown.basis) == (
        0.0,
        "sin prevision: aun no ha jugado esta temporada",
    )


def test_on_equal_totals_the_higher_ceiling_wins() -> None:
    # The fourth defender and the third forward are worth the same 3.5, so
    # 1-4-4-2 and 1-3-4-3 add the same; the one with the wider spread wins.
    flat = squad(p32=c(32, "DEL", 3.5, spread=4.0), p33=c(33, "DEL", 1.0))
    s = best_lineup(flat, [f for f in FORMATIONS if f.name in ("1-4-4-2", "1-3-4-3")])
    assert s is not None and s.formation == "1-3-4-3"
    narrow = squad(p13=c(13, "DEF", 3.5, spread=4.0), p32=c(32, "DEL", 3.5), p33=c(33, "DEL", 1.0))
    s = best_lineup(narrow, [f for f in FORMATIONS if f.name in ("1-4-4-2", "1-3-4-3")])
    assert s is not None and s.formation == "1-4-4-2"


def test_a_formation_can_be_imposed_and_an_unfillable_one_gives_nothing() -> None:
    s = best_lineup(squad(), FORMATIONS, only="1-5-4-1")
    assert s is not None and s.formation == "1-5-4-1"
    assert best_lineup(squad(), FORMATIONS, only="1-2-2-6") is None
    no_keeper = [x for x in squad() if x.position != "POR"]
    assert best_lineup(no_keeper, FORMATIONS) is None
