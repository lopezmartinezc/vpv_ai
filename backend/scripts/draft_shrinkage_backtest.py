"""Offline backtest: does blending early-season (4-8 md) data with historical
priors beat the current cold-start draft model?

Reads the legacy MySQL dump (jornadas_temp) loaded in the vpv-mysql-source
container. For each test season T and draft cutoff K, it predicts each
candidate's REST-OF-SEASON points (md > K) with several models and reports
the Spearman rank correlation vs the actual rest-of-season points.

Nothing here touches the app; it's a pure validation harness to pick the
shrinkage constant k and prove the early-season blend helps.
"""

from __future__ import annotations

import statistics
from collections import defaultdict

import mysql.connector

conn = mysql.connector.connect(
    host="127.0.0.1", port=3307, user="root", password="migration", database="ligavpv"
)
cur = conn.cursor()
# All player-matchday rows. Treat NULL points/minutes as 0. Position per row.
cur.execute(
    """
    SELECT nom_url, temporada, jornada, pos,
           COALESCE(tiempo_jug,0), COALESCE(ptos_jor,0),
           COALESCE(gol,0)+COALESCE(gol_p,0), COALESCE(asis,0)
    FROM jornadas_temp
    """
)
rows = cur.fetchall()
cur.close()
conn.close()

# ---- Organize per (slug, season) ----
# season order by name (chronological)
seasons_sorted = sorted({r[1] for r in rows})
season_idx = {s: i for i, s in enumerate(seasons_sorted)}

# per (slug, season): list of (matchday, minutes, pts, ga, pos)
bucket: dict[tuple[str, str], list] = defaultdict(list)
for slug, season, md, pos, mins, pts, ga, _asis in rows:
    bucket[(slug, season)].append((int(md), int(mins), float(pts), int(ga), pos))


def agg(records, md_min=None, md_max=None):
    """Aggregate a player's rows in a matchday window."""
    sel = [
        r
        for r in records
        if (md_min is None or r[0] >= md_min) and (md_max is None or r[0] <= md_max)
    ]
    if not sel:
        return None
    pts = [r[2] for r in sel]
    mins = [r[1] for r in sel]
    positions = [r[4] for r in sel]
    games = len(sel)
    return {
        "games": games,
        "games_45": sum(1 for m in mins if m >= 45),
        "avg": statistics.mean(pts),
        "total": sum(pts),
        "std": statistics.pstdev(pts) if games > 1 else 0.0,
        "minutes": sum(mins),
        "goals": sum(r[3] for r in sel),
        "assists": 0,  # not needed for the core models
        "pos": statistics.mode(positions),
        "sh_avg": (
            statistics.mean([r[2] for r in sel if r[0] > 19])
            if any(r[0] > 19 for r in sel)
            else 0.0
        ),
    }


# Full-season aggregate per (slug, season)
full_agg: dict[tuple[str, str], dict] = {}
for key, recs in bucket.items():
    a = agg(recs)
    if a:
        full_agg[key] = a


def career_ensemble(hist_aggs):
    """Model V (current cold-start ensemble) from a list of prior-season aggs,
    ordered oldest->newest. Mirrors service_draft.py."""
    if not hist_aggs:
        return None
    last = hist_aggs[-1]
    simple_avg = last["avg"]
    # stability
    starter_rates = [h["games_45"] / max(h["games"], 1) for h in hist_aggs]
    avg_starter = statistics.mean(starter_rates)
    career_avg = statistics.mean(h["avg"] for h in hist_aggs)
    stability = career_avg * (0.8 + avg_starter * 0.4)
    components = [simple_avg, stability]
    # trend
    if len(hist_aggs) >= 2 and hist_aggs[-2]["avg"] > 0:
        tr = (hist_aggs[-1]["avg"] - hist_aggs[-2]["avg"]) / hist_aggs[-2]["avg"]
        components.append(career_avg * (1 + tr * 0.5))
    elif hist_aggs:
        components.append(last["avg"])
    # second half
    if last["sh_avg"] > 0:
        components.append(last["sh_avg"] * 0.6 + last["avg"] * 0.4)
    else:
        components.append(last["avg"])
    return statistics.mean(components)


def spearman(xs, ys):
    n = len(xs)
    if n < 3:
        return None

    def ranks(vals):
        order = sorted(range(n), key=lambda i: vals[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg_rank = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg_rank
            i = j + 1
        return r

    rx, ry = ranks(xs), ranks(ys)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    den = (
        sum((rx[i] - mx) ** 2 for i in range(n)) ** 0.5
        * sum((ry[i] - my) ** 2 for i in range(n)) ** 0.5
    )
    return num / den if den else None


# ---- Backtest ----
# Test seasons: any season that has >=1 prior season.
test_seasons = [s for s in seasons_sorted if season_idx[s] >= 1]
# Drop the partial current season (2025-2026) as a TEST target (rest-of-season
# truncated) but keep it usable as history for nothing later. Simplest: only
# test complete seasons.
COMPLETE = [s for s in test_seasons if s != "2025-2026"]

K_VALUES = [4, 6, 8]
K_SHRINK = [0, 2, 3, 4, 6, 8, 10, 15, 999]  # 0 = current-only, 999 = history-only
MIN_CUR_GAMES = 2  # candidate must have >=2 of the first K games

print(f"seasons={seasons_sorted}")
print(f"test(complete)={COMPLETE}\n")

# results[K][k] = list of per-season spearman
results = defaultdict(lambda: defaultdict(list))
counts = defaultdict(list)

for T in COMPLETE:
    priors = [s for s in seasons_sorted if season_idx[s] < season_idx[T]]
    for K in K_VALUES:
        preds_by_k = defaultdict(list)
        targets = []
        # candidate slugs: appear in first K md of T
        cand = []
        for (slug, season), recs in bucket.items():
            if season != T:
                continue
            cur_a = agg(recs, md_min=1, md_max=K)
            if not cur_a or cur_a["games"] < MIN_CUR_GAMES:
                continue
            rest = agg(recs, md_min=K + 1, md_max=38)
            target = rest["total"] if rest else 0.0
            hist = [full_agg[(slug, s)] for s in priors if (slug, s) in full_agg]
            cand.append((slug, cur_a, hist, target))

        for _slug, cur_a, hist, target in cand:
            career = career_ensemble(hist)
            n_cur = cur_a["games"]
            cur_avg = cur_a["avg"]
            targets.append(target)
            for k in K_SHRINK:
                if k == 0:  # current-only
                    pred = cur_avg
                elif k == 999:  # history-only (current cold-start model)
                    pred = career if career is not None else cur_avg
                else:  # empirical-Bayes shrinkage blend
                    if career is None:
                        pred = cur_avg
                    else:
                        w = n_cur / (n_cur + k)
                        pred = career * (1 - w) + cur_avg * w
                preds_by_k[k].append(pred)

        for k in K_SHRINK:
            rho = spearman(preds_by_k[k], targets)
            if rho is not None:
                results[K][k].append(rho)
        counts[K].append(len(targets))

# ---- Report ----
label = {0: "current-only", 999: "history-only(baseline)"}
print("Spearman(pred, rest-of-season pts), mean over complete test seasons\n")
header = "K(md)  N/season  " + "  ".join(f"{label.get(k, f'k={k}'):>16}" for k in K_SHRINK)
print(header)
for K in K_VALUES:
    navg = int(statistics.mean(counts[K]))
    cells = []
    for k in K_SHRINK:
        vals = results[K][k]
        cells.append(f"{statistics.mean(vals):>16.3f}" if vals else f"{'-':>16}")
    print(f"{K:>4}  {navg:>8}  " + "  ".join(cells))

print("\nPer-season detail (K=6):")
for i, T in enumerate(COMPLETE):
    base = results[6][999][i] if i < len(results[6][999]) else None
    best_k = max(
        [k for k in K_SHRINK if k not in (0, 999)],
        key=lambda k: results[6][k][i] if i < len(results[6][k]) else -1,
    )
    bestv = results[6][best_k][i]
    print(f"  {T}: baseline={base:.3f}  best_blend(k={best_k})={bestv:.3f}")
