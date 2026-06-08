"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { useSeason } from "@/contexts/season-context";
import { apiClient } from "@/lib/api-client";
import type {
  CompetitionListResponse,
  CompetitionMatchupsResponse,
  CompetitionStandingsResponse,
  GroupStandings,
  MatchupEntry,
} from "@/types";

type Tab = "standings" | "calendar" | "ko";

export default function PlayoffsPage() {
  const { selectedSeason, loading: seasonLoading } = useSeason();
  const [competitionId, setCompetitionId] = useState<number | null>(null);
  const [standings, setStandings] = useState<CompetitionStandingsResponse | null>(null);
  const [matchups, setMatchups] = useState<CompetitionMatchupsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("standings");

  const load = useCallback(async () => {
    if (!selectedSeason) return;
    setLoading(true);
    setError(null);
    try {
      const list = await apiClient.get<CompetitionListResponse>(
        `/competitions/season/${selectedSeason.id}`,
      );
      const playoff = list.competitions.find((c) => c.type === "playoff");
      if (!playoff) {
        setCompetitionId(null);
        setStandings(null);
        setMatchups(null);
        return;
      }
      setCompetitionId(playoff.id);
      const [s, m] = await Promise.all([
        apiClient.get<CompetitionStandingsResponse>(
          `/competitions/${playoff.id}/standings`,
        ),
        apiClient.get<CompetitionMatchupsResponse>(
          `/competitions/${playoff.id}/matchups`,
        ),
      ]);
      setStandings(s);
      setMatchups(m);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error cargando playoff");
    } finally {
      setLoading(false);
    }
  }, [selectedSeason]);

  useEffect(() => {
    load();
  }, [load]);

  // Lightweight polling: refresh every 60s so the public page picks up
  // scraping updates without a manual reload.
  useEffect(() => {
    if (!competitionId) return;
    const handle = setInterval(load, 60_000);
    return () => clearInterval(handle);
  }, [competitionId, load]);

  if (seasonLoading) {
    return <div className="h-8 w-40 animate-pulse rounded bg-vpv-border" />;
  }

  if (!selectedSeason) {
    return (
      <p className="text-sm text-vpv-text-muted">
        Selecciona una temporada para ver el playoff.
      </p>
    );
  }

  if (loading && !standings) {
    return <p className="text-sm text-vpv-text-muted">Cargando playoff…</p>;
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
        {error}
      </div>
    );
  }

  if (!competitionId || !standings || !matchups) {
    return (
      <p className="text-sm text-vpv-text-muted">
        Esta temporada aún no tiene playoff configurado.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-bold text-vpv-text">
            {standings.competition.name}
          </h1>
          <p className="text-xs text-vpv-text-muted">
            Estado:{" "}
            <span className="text-vpv-text">{standings.competition.status}</span>
          </p>
        </div>
      </header>

      <nav className="flex gap-2">
        {(["standings", "calendar", "ko"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
              tab === t
                ? "bg-vpv-accent text-vpv-bg"
                : "bg-vpv-card text-vpv-text-muted hover:text-vpv-text"
            }`}
          >
            {t === "standings"
              ? "Clasificación"
              : t === "calendar"
                ? "Calendario"
                : "Eliminatorias"}
          </button>
        ))}
      </nav>

      {tab === "standings" && <StandingsView groups={standings.groups} />}
      {tab === "calendar" && <CalendarView matchups={matchups.matchups} />}
      {tab === "ko" && <KoView matchups={matchups.matchups} />}
    </div>
  );
}

function StandingsView({ groups }: { groups: GroupStandings[] }) {
  if (groups.length === 0) {
    return <p className="text-sm text-vpv-text-muted">Sin clasificación aún.</p>;
  }
  return (
    <div className={`grid gap-4 ${groups.length > 1 ? "md:grid-cols-2" : ""}`}>
      {groups.map((g) => (
        <div key={g.label} className="rounded-lg border border-vpv-card-border bg-vpv-card">
          {groups.length > 1 && (
            <div className="border-b border-vpv-card-border px-3 py-2 text-xs font-semibold uppercase tracking-wide text-vpv-text-muted">
              Grupo {g.label}
            </div>
          )}
          <table className="w-full text-xs">
            <thead className="bg-vpv-bg/40 text-vpv-text-muted">
              <tr>
                <th className="px-2 py-1 text-left">#</th>
                <th className="px-2 py-1 text-left">Participante</th>
                <th className="px-2 py-1 text-center">J</th>
                <th className="px-2 py-1 text-center">G</th>
                <th className="px-2 py-1 text-center">E</th>
                <th className="px-2 py-1 text-center">P</th>
                <th className="px-2 py-1 text-center">D</th>
                <th className="px-2 py-1 text-center">Dif</th>
                <th className="px-2 py-1 text-center font-semibold text-vpv-text">Pts</th>
              </tr>
            </thead>
            <tbody>
              {g.entries.map((e) => (
                <tr key={e.participant_id} className="border-t border-vpv-border/50">
                  <td className="px-2 py-1 text-vpv-text-muted">{e.rank}</td>
                  <td className="px-2 py-1 text-vpv-text">{e.display_name}</td>
                  <td className="px-2 py-1 text-center">{e.played}</td>
                  <td className="px-2 py-1 text-center">{e.wins}</td>
                  <td className="px-2 py-1 text-center">{e.draws}</td>
                  <td className="px-2 py-1 text-center">{e.losses}</td>
                  <td className="px-2 py-1 text-center text-vpv-text-muted">{e.rests}</td>
                  <td
                    className="px-2 py-1 text-center"
                    title={`pts VPV totales: ${e.pts_total_vpv}`}
                  >
                    {e.diff_avg > 0 ? `+${e.diff_avg}` : e.diff_avg}
                  </td>
                  <td className="px-2 py-1 text-center font-bold text-vpv-accent">{e.points}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}

function CalendarView({ matchups }: { matchups: MatchupEntry[] }) {
  const regularByRound = useMemo(() => {
    const out = new Map<number, MatchupEntry[]>();
    matchups
      .filter((m) => m.phase === "regular")
      .forEach((m) => {
        const list = out.get(m.round_number) ?? [];
        list.push(m);
        out.set(m.round_number, list);
      });
    return out;
  }, [matchups]);

  const sortedRounds = [...regularByRound.keys()].sort((a, b) => a - b);

  if (sortedRounds.length === 0) {
    return <p className="text-sm text-vpv-text-muted">Sin cruces aún.</p>;
  }

  return (
    <div className="space-y-3">
      {sortedRounds.map((round) => {
        const list = regularByRound.get(round) ?? [];
        return (
          <div key={round} className="rounded-lg border border-vpv-card-border bg-vpv-card">
            <div className="border-b border-vpv-card-border px-3 py-2 text-xs font-semibold text-vpv-text-muted">
              Jornada {round}
              {list[0]?.matchday_number && (
                <span className="ml-2 text-vpv-text-muted/60">
                  (Mundial J{list[0].matchday_number})
                </span>
              )}
            </div>
            <ul className="divide-y divide-vpv-border/40">
              {list.map((m) => (
                <li key={m.id} className="flex items-center justify-between px-3 py-1.5 text-xs">
                  <span
                    className={`flex-1 truncate ${
                      m.winner_participant_id === m.participant_a_id
                        ? "font-bold text-vpv-text"
                        : "text-vpv-text"
                    }`}
                  >
                    {m.participant_a_name ?? "?"}
                  </span>
                  <span className="mx-3 tabular-nums text-vpv-text-muted">
                    {m.score_a ?? "—"} — {m.score_b ?? "—"}
                  </span>
                  <span
                    className={`flex-1 truncate text-right ${
                      m.winner_participant_id === m.participant_b_id
                        ? "font-bold text-vpv-text"
                        : "text-vpv-text"
                    }`}
                  >
                    {m.participant_b_name ?? "?"}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}

function KoView({ matchups }: { matchups: MatchupEntry[] }) {
  const koByLabel = useMemo(() => {
    const out = new Map<string, MatchupEntry[]>();
    matchups
      .filter((m) => m.phase === "ko")
      .forEach((m) => {
        const label = m.round_label ?? "ko";
        const list = out.get(label) ?? [];
        list.push(m);
        out.set(label, list);
      });
    return out;
  }, [matchups]);

  const orderedLabels = ["quarter", "semi", "final"].filter((l) => koByLabel.has(l));

  if (orderedLabels.length === 0) {
    return (
      <p className="text-sm text-vpv-text-muted">
        Las eliminatorias aún no han comenzado.
      </p>
    );
  }

  return (
    <div className="grid gap-4 md:grid-cols-3">
      {orderedLabels.map((label) => (
        <div key={label} className="rounded-lg border border-vpv-card-border bg-vpv-card">
          <div className="border-b border-vpv-card-border px-3 py-2 text-xs font-semibold uppercase tracking-wide text-vpv-text-muted">
            {label === "quarter" ? "Cuartos" : label === "semi" ? "Semifinales" : "Final"}
          </div>
          <ul className="divide-y divide-vpv-border/40">
            {(koByLabel.get(label) ?? []).map((m) => (
              <li key={m.id} className="px-3 py-2 text-xs">
                <div className="flex items-center justify-between">
                  <span
                    className={`flex-1 truncate ${
                      m.winner_participant_id === m.participant_a_id
                        ? "font-bold text-vpv-text"
                        : "text-vpv-text"
                    }`}
                  >
                    {m.participant_a_name ?? "Pendiente"}
                  </span>
                  <span className="mx-3 tabular-nums text-vpv-text-muted">
                    {m.score_a ?? "—"} — {m.score_b ?? "—"}
                  </span>
                  <span
                    className={`flex-1 truncate text-right ${
                      m.winner_participant_id === m.participant_b_id
                        ? "font-bold text-vpv-text"
                        : "text-vpv-text"
                    }`}
                  >
                    {m.participant_b_name ?? "Pendiente"}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
