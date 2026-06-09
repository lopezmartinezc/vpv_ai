"use client";

/**
 * Draft Retro — admin analytics tab.
 *
 * Four sub-views over the same conceptual question: "did the draft
 * actually produce what the model said it would?"
 *
 *  1. Retrospectiva — pick-by-pick post-mortem of one draft
 *  2. Scatter     — every pick across seasons, with steal/bust trendline
 *  3. Backtest    — replay the scorecard against a completed season
 *  4. Draft IQ    — per-participant ranking by mean delta-vs-slot
 *
 * Backend endpoints: /stats/admin/drafts/*
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Cell,
  Legend,
  Line,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
  ComposedChart,
} from "recharts";

import { apiClient } from "@/lib/api-client";
import type {
  BacktestResponse,
  DraftListResponse,
  DraftRetrospectiveResponse,
  DraftScatterResponse,
  ParticipantIQResponse,
  RetroPick,
} from "@/types";
import {
  POSITION_COLORS,
  POSITION_HEX,
  SIGNAL_LABELS,
  TAG_COLORS,
  TAG_LABELS,
  TIER_COLORS,
  TIER_LABELS,
} from "@/lib/draft-scorecard";

type SubTab = "retrospectiva" | "scatter" | "backtest" | "iq";

interface SeasonOption {
  id: number;
  name: string;
}

interface Props {
  seasons: SeasonOption[];
  defaultSeasonId: number | null;
}

export function DraftRetroTab({ seasons, defaultSeasonId }: Props) {
  const [sub, setSub] = useState<SubTab>("retrospectiva");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-1">
        {(
          [
            { key: "retrospectiva", label: "Retrospectiva" },
            { key: "scatter", label: "Scatter histórico" },
            { key: "backtest", label: "Backtest" },
            { key: "iq", label: "Draft IQ" },
          ] as const
        ).map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setSub(key)}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              sub === key
                ? "bg-vpv-accent text-white"
                : "bg-vpv-card text-vpv-text-muted hover:text-vpv-text"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {sub === "retrospectiva" && (
        <RetrospectivaSubTab seasons={seasons} defaultSeasonId={defaultSeasonId} />
      )}
      {sub === "scatter" && <ScatterSubTab seasons={seasons} />}
      {sub === "backtest" && (
        <BacktestSubTab seasons={seasons} defaultSeasonId={defaultSeasonId} />
      )}
      {sub === "iq" && <DraftIQSubTab />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// 1. Retrospectiva — pick-by-pick post-mortem of one draft
// ---------------------------------------------------------------------------

function RetrospectivaSubTab({
  seasons,
  defaultSeasonId,
}: {
  seasons: SeasonOption[];
  defaultSeasonId: number | null;
}) {
  const [seasonId, setSeasonId] = useState<number | null>(defaultSeasonId);
  const [drafts, setDrafts] = useState<DraftListResponse | null>(null);
  const [selectedDraftId, setSelectedDraftId] = useState<number | null>(null);
  const [data, setData] = useState<DraftRetrospectiveResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<"" | "steal" | "bust" | "normal">("");
  const [posFilter, setPosFilter] = useState<string>("");
  const [participantFilter, setParticipantFilter] = useState<string>("");

  // Reset selected draft when season changes.
  useEffect(() => {
    setSelectedDraftId(null);
    setData(null);
  }, [seasonId]);

  useEffect(() => {
    if (seasonId === null) return;
    setLoading(true);
    apiClient
      .get<DraftListResponse>(`/drafts/${seasonId}`)
      .then((d) => {
        setDrafts(d);
        // Auto-select the preseason draft if there's only one or it's
        // the obvious choice.
        const pre = d.drafts.find((x) => x.phase === "preseason");
        if (pre) setSelectedDraftId(pre.id);
      })
      .catch(() => setDrafts(null))
      .finally(() => setLoading(false));
  }, [seasonId]);

  useEffect(() => {
    if (selectedDraftId === null) {
      setData(null);
      return;
    }
    setLoading(true);
    apiClient
      .get<DraftRetrospectiveResponse>(
        `/stats/admin/drafts/${selectedDraftId}/retrospective`,
      )
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [selectedDraftId]);

  const participants = useMemo(() => {
    if (!data) return [];
    return Array.from(
      new Set(data.picks.map((p) => p.participant_display_name)),
    ).sort();
  }, [data]);

  const filtered = useMemo(() => {
    if (!data) return [];
    return data.picks.filter(
      (p) =>
        (!filter || p.tag === filter) &&
        (!posFilter || p.position === posFilter) &&
        (!participantFilter || p.participant_display_name === participantFilter),
    );
  }, [data, filter, posFilter, participantFilter]);

  return (
    <div className="space-y-3">
      {/* Selectors */}
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-xs text-vpv-text-muted">Temporada</label>
        <select
          value={seasonId ?? ""}
          onChange={(e) => setSeasonId(Number(e.target.value))}
          className="rounded border border-vpv-border bg-vpv-bg px-2 py-1 text-xs text-vpv-text"
        >
          {seasons.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>

        <label className="text-xs text-vpv-text-muted">Draft</label>
        <select
          value={selectedDraftId ?? ""}
          onChange={(e) =>
            setSelectedDraftId(e.target.value ? Number(e.target.value) : null)
          }
          disabled={!drafts || drafts.drafts.length === 0}
          className="rounded border border-vpv-border bg-vpv-bg px-2 py-1 text-xs text-vpv-text"
        >
          <option value="">— Selecciona —</option>
          {drafts?.drafts.map((d) => (
            <option key={d.id} value={d.id}>
              {d.phase} · {d.status}
            </option>
          ))}
        </select>
      </div>

      {data && (
        <div className="flex flex-wrap items-center gap-3 text-xs">
          <span className="text-vpv-text-muted">Filtros:</span>
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value as typeof filter)}
            className="rounded border border-vpv-border bg-vpv-bg px-2 py-1 text-vpv-text"
          >
            <option value="">Todos los tags</option>
            <option value="steal">💎 Steal</option>
            <option value="bust">⚠️ Bust</option>
            <option value="normal">Normal</option>
          </select>
          <select
            value={posFilter}
            onChange={(e) => setPosFilter(e.target.value)}
            className="rounded border border-vpv-border bg-vpv-bg px-2 py-1 text-vpv-text"
          >
            <option value="">Todas las posiciones</option>
            {["POR", "DEF", "MED", "DEL"].map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
          <select
            value={participantFilter}
            onChange={(e) => setParticipantFilter(e.target.value)}
            className="rounded border border-vpv-border bg-vpv-bg px-2 py-1 text-vpv-text"
          >
            <option value="">Todos los participantes</option>
            {participants.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>
      )}

      {loading && (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="h-10 animate-pulse rounded-lg bg-vpv-border"
            />
          ))}
        </div>
      )}

      {!loading && data && data.picks.length === 0 && (
        <p className="rounded-lg border border-vpv-card-border bg-vpv-card p-4 text-sm text-vpv-text-muted">
          Este draft aún no tiene picks o no hay datos de temporada.
        </p>
      )}

      {!loading && data && data.picks.length > 0 && (
        <RetroPickTable picks={filtered} />
      )}
    </div>
  );
}

function RetroPickTable({ picks }: { picks: RetroPick[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-vpv-card-border bg-vpv-card">
      <table className="min-w-full text-xs">
        <thead className="border-b border-vpv-card-border bg-vpv-bg/40 text-vpv-text-muted">
          <tr>
            <th className="px-2 py-2 text-left">#</th>
            <th className="px-2 py-2 text-left">R</th>
            <th className="px-2 py-2 text-left">Pos</th>
            <th className="px-2 py-2 text-left">Jugador</th>
            <th className="px-2 py-2 text-left">Equipo</th>
            <th className="px-2 py-2 text-left">Participante</th>
            <th className="px-2 py-2 text-right" title="Puntos totales en la temporada del draft">
              Pts
            </th>
            <th className="px-2 py-2 text-right" title="Mediana del slot (pick) en seasons históricas">
              Slot
            </th>
            <th className="px-2 py-2 text-right" title="Pts − Slot. Positivo = mejor que el slot histórico">
              Δ
            </th>
            <th className="px-2 py-2 text-center">Tag</th>
          </tr>
        </thead>
        <tbody>
          {picks.map((p) => (
            <tr
              key={`${p.pick_number}-${p.player_id}`}
              className="border-b border-vpv-card-border/40 last:border-0 hover:bg-vpv-bg/40"
            >
              <td className="px-2 py-1.5 font-mono text-vpv-text">{p.pick_number}</td>
              <td className="px-2 py-1.5 text-vpv-text-muted">{p.round_number}</td>
              <td className="px-2 py-1.5">
                <span className={`rounded px-1.5 py-px text-[10px] font-bold ${POSITION_COLORS[p.position] ?? ""}`}>
                  {p.position}
                </span>
              </td>
              <td className="px-2 py-1.5 text-vpv-text">{p.player_name}</td>
              <td className="px-2 py-1.5 text-vpv-text-muted">{p.team_name}</td>
              <td className="px-2 py-1.5 text-vpv-text-muted">{p.participant_display_name}</td>
              <td className="px-2 py-1.5 text-right tabular-nums text-vpv-text">{p.season_total_points}</td>
              <td className="px-2 py-1.5 text-right tabular-nums text-vpv-text-muted">
                {p.slot_median_total_points ?? "—"}
              </td>
              <td
                className={`px-2 py-1.5 text-right tabular-nums font-bold ${
                  p.delta_vs_slot === null
                    ? "text-vpv-text-muted"
                    : p.delta_vs_slot > 0
                      ? "text-emerald-400"
                      : p.delta_vs_slot < 0
                        ? "text-red-400"
                        : "text-vpv-text"
                }`}
              >
                {p.delta_vs_slot === null
                  ? "—"
                  : p.delta_vs_slot > 0
                    ? `+${p.delta_vs_slot}`
                    : p.delta_vs_slot}
              </td>
              <td className="px-2 py-1.5 text-center">
                <span className={`rounded px-1.5 py-px text-[10px] font-bold ${TAG_COLORS[p.tag] ?? ""}`}>
                  {TAG_LABELS[p.tag] ?? p.tag}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 2. Scatter histórico — every pick across seasons
// ---------------------------------------------------------------------------

function ScatterSubTab({ seasons }: { seasons: SeasonOption[] }) {
  const [selected, setSelected] = useState<Set<number>>(
    new Set(seasons.map((s) => s.id)),
  );
  const [data, setData] = useState<DraftScatterResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [posFilter, setPosFilter] = useState<string>("");

  const fetchData = useCallback(async () => {
    setLoading(true);
    const ids = Array.from(selected).sort().join(",");
    try {
      const d = await apiClient.get<DraftScatterResponse>(
        `/stats/admin/drafts/scatter?season_ids=${ids}`,
      );
      setData(d);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [selected]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const points = useMemo(() => {
    if (!data) return [];
    return data.points.filter((p) => !posFilter || p.position === posFilter);
  }, [data, posFilter]);

  const trendLine = useMemo(() => {
    if (!data) return [];
    return Object.entries(data.slot_curve)
      .map(([pn, val]) => ({ pick_number: Number(pn), slot: val }))
      .sort((a, b) => a.pick_number - b.pick_number);
  }, [data]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3 text-xs">
        <span className="text-vpv-text-muted">Temporadas:</span>
        {seasons.map((s) => (
          <label key={s.id} className="flex items-center gap-1 text-vpv-text">
            <input
              type="checkbox"
              checked={selected.has(s.id)}
              onChange={(e) => {
                const next = new Set(selected);
                if (e.target.checked) next.add(s.id);
                else next.delete(s.id);
                setSelected(next);
              }}
            />
            {s.name}
          </label>
        ))}
        <span className="text-vpv-text-muted">Posición:</span>
        <select
          value={posFilter}
          onChange={(e) => setPosFilter(e.target.value)}
          className="rounded border border-vpv-border bg-vpv-bg px-2 py-1 text-vpv-text"
        >
          <option value="">Todas</option>
          {["POR", "DEF", "MED", "DEL"].map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
      </div>

      {loading && (
        <div className="h-80 animate-pulse rounded-lg bg-vpv-border" />
      )}

      {!loading && data && (
        <>
          <p className="text-xs text-vpv-text-muted">
            {data.n_points} picks · cada punto es un jugador drafteado. La
            línea es la mediana del slot — picks por encima son{" "}
            <span className="text-emerald-300">steals</span>, por debajo son{" "}
            <span className="text-red-300">busts</span>.
          </p>
          <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-3">
            <ResponsiveContainer width="100%" height={420}>
              <ComposedChart>
                <CartesianGrid stroke="#27272a" strokeDasharray="3 3" />
                <XAxis
                  type="number"
                  dataKey="pick_number"
                  name="Pick"
                  domain={[0, "dataMax + 1"]}
                  stroke="#a1a1aa"
                  label={{ value: "Pick #", position: "insideBottomRight", offset: -4, fill: "#a1a1aa" }}
                />
                <YAxis
                  type="number"
                  dataKey="total_points"
                  name="Pts temporada"
                  stroke="#a1a1aa"
                  label={{ value: "Pts temporada", angle: -90, position: "insideLeft", fill: "#a1a1aa" }}
                />
                <ZAxis range={[30, 30]} />
                <Tooltip content={<ScatterTooltip />} />
                <Legend />
                {["POR", "DEF", "MED", "DEL"].map((pos) => {
                  const subset = points.filter((p) => p.position === pos);
                  if (subset.length === 0) return null;
                  return (
                    <Scatter key={pos} name={pos} data={subset} fill={POSITION_HEX[pos]}>
                      {subset.map((_, i) => (
                        <Cell key={i} fill={POSITION_HEX[pos]} />
                      ))}
                    </Scatter>
                  );
                })}
                <Line
                  data={trendLine}
                  type="monotone"
                  dataKey="slot"
                  stroke="#fbbf24"
                  strokeWidth={2}
                  dot={false}
                  name="Mediana del slot"
                  isAnimationActive={false}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  );
}

interface ScatterPayload {
  pick_number: number;
  total_points: number;
  player_name: string;
  team_name: string;
  position: string;
  season_name: string;
  participant_display_name: string;
}

function ScatterTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: ScatterPayload }>;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const p = payload[0].payload;
  if (!p || p.player_name === undefined) return null;
  return (
    <div className="rounded-md border border-vpv-card-border bg-vpv-bg px-2 py-1.5 text-[11px] text-vpv-text shadow-lg">
      <div className="font-bold">
        {p.player_name}{" "}
        <span className={`ml-1 rounded px-1 py-px text-[9px] font-bold ${POSITION_COLORS[p.position] ?? ""}`}>
          {p.position}
        </span>
      </div>
      <div className="text-vpv-text-muted">{p.team_name} · {p.season_name}</div>
      <div>
        Pick <span className="font-bold">{p.pick_number}</span> ·{" "}
        <span className="font-bold tabular-nums">{p.total_points} pts</span>
      </div>
      <div className="text-vpv-text-muted">→ {p.participant_display_name}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 3. Backtest — scorecard replayed against a completed season
// ---------------------------------------------------------------------------

function BacktestSubTab({
  seasons,
  defaultSeasonId,
}: {
  seasons: SeasonOption[];
  defaultSeasonId: number | null;
}) {
  const [seasonId, setSeasonId] = useState<number | null>(defaultSeasonId);
  const [data, setData] = useState<BacktestResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (seasonId === null) return;
    setLoading(true);
    setError(null);
    apiClient
      .get<BacktestResponse>(`/stats/admin/drafts/backtest?season_id=${seasonId}`)
      .then((d) => {
        setData(d);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Error desconocido");
        setData(null);
      })
      .finally(() => setLoading(false));
  }, [seasonId]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3 text-xs">
        <label className="text-vpv-text-muted">Temporada a backtestear</label>
        <select
          value={seasonId ?? ""}
          onChange={(e) => setSeasonId(Number(e.target.value))}
          className="rounded border border-vpv-border bg-vpv-bg px-2 py-1 text-vpv-text"
        >
          {seasons.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
        <span className="text-vpv-text-muted">
          (Backtest = predicción usando sólo temporadas anteriores)
        </span>
      </div>

      {loading && (
        <div className="grid gap-3 sm:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-24 animate-pulse rounded-lg bg-vpv-border" />
          ))}
        </div>
      )}

      {error && (
        <p className="rounded border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-300">
          {error}
        </p>
      )}

      {!loading && data && (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-3">
              <p className="text-[10px] uppercase tracking-wider text-vpv-text-muted">
                Spearman ρ
              </p>
              <p className="mt-1 text-2xl font-bold text-vpv-accent">
                {data.spearman_rank_correlation.toFixed(3)}
              </p>
              <p className="text-[10px] text-vpv-text-muted">
                Predicción vs real ({data.n_players} jugadores)
              </p>
            </div>
            <BucketCard
              title="Por signal"
              buckets={data.by_signal}
              order={["strong_buy", "buy", "hold", "avoid"]}
              labelFor={(k) => SIGNAL_LABELS[k]?.label ?? k}
              classFor={(k) => SIGNAL_LABELS[k]?.classes ?? ""}
            />
            <BucketCard
              title="Por tier"
              buckets={data.by_tier}
              order={["elite", "solid", "normal", "weak"]}
              labelFor={(k) => TIER_LABELS[k] ?? k}
              classFor={(k) => TIER_COLORS[k] ?? ""}
            />
          </div>

          <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
            <table className="min-w-full text-xs">
              <thead className="border-b border-vpv-card-border bg-vpv-bg/40 text-vpv-text-muted">
                <tr>
                  <th className="px-2 py-2 text-left">Pos</th>
                  <th className="px-2 py-2 text-left">Jugador</th>
                  <th className="px-2 py-2 text-right">xPts</th>
                  <th className="px-2 py-2 text-center">Signal</th>
                  <th className="px-2 py-2 text-center">Tier</th>
                  <th className="px-2 py-2 text-right">Real</th>
                  <th className="px-2 py-2 text-right">PJ</th>
                </tr>
              </thead>
              <tbody>
                {data.points.slice(0, 80).map((p) => (
                  <tr
                    key={p.player_id}
                    className="border-b border-vpv-card-border/40 last:border-0 hover:bg-vpv-bg/40"
                  >
                    <td className="px-2 py-1.5">
                      <span className={`rounded px-1.5 py-px text-[10px] font-bold ${POSITION_COLORS[p.position] ?? ""}`}>
                        {p.position}
                      </span>
                    </td>
                    <td className="px-2 py-1.5 text-vpv-text">{p.player_name}</td>
                    <td className="px-2 py-1.5 text-right tabular-nums font-bold text-vpv-accent">
                      {p.predicted_effective_score.toFixed(2)}
                    </td>
                    <td className="px-2 py-1.5 text-center">
                      <span className={`rounded px-1 py-px text-[9px] font-bold ${SIGNAL_LABELS[p.predicted_signal]?.classes ?? ""}`}>
                        {SIGNAL_LABELS[p.predicted_signal]?.label ?? p.predicted_signal}
                      </span>
                    </td>
                    <td className="px-2 py-1.5 text-center">
                      <span className={`rounded px-1 py-px text-[9px] font-bold ${TIER_COLORS[p.predicted_tier] ?? ""}`}>
                        {TIER_LABELS[p.predicted_tier] ?? p.predicted_tier}
                      </span>
                    </td>
                    <td className="px-2 py-1.5 text-right tabular-nums text-vpv-text">
                      {p.actual_total_points}
                    </td>
                    <td className="px-2 py-1.5 text-right tabular-nums text-vpv-text-muted">
                      {p.actual_matchdays_played}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {data.points.length > 80 && (
              <p className="border-t border-vpv-card-border px-3 py-2 text-[10px] text-vpv-text-muted">
                Mostrando los 80 primeros por predicted_effective_score. Total: {data.n_players}.
              </p>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function BucketCard({
  title,
  buckets,
  order,
  labelFor,
  classFor,
}: {
  title: string;
  buckets: BacktestResponse["by_signal"];
  order: string[];
  labelFor: (k: string) => string;
  classFor: (k: string) => string;
}) {
  return (
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-3">
      <p className="mb-2 text-[10px] uppercase tracking-wider text-vpv-text-muted">{title}</p>
      <div className="space-y-1">
        {order.map((k) => {
          const b = buckets[k];
          if (!b) return null;
          return (
            <div key={k} className="flex items-center justify-between gap-2 text-xs">
              <span className={`rounded px-1 py-px text-[9px] font-bold ${classFor(k)}`}>
                {labelFor(k)}
              </span>
              <span className="tabular-nums text-vpv-text-muted">
                n={b.n} · med={b.median_actual}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 4. Draft IQ — per-participant ranking
// ---------------------------------------------------------------------------

function DraftIQSubTab() {
  const [phase, setPhase] = useState<"preseason" | "winter">("preseason");
  const [minSeasons, setMinSeasons] = useState(2);
  const [data, setData] = useState<ParticipantIQResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState<number | null>(null);

  useEffect(() => {
    setLoading(true);
    apiClient
      .get<ParticipantIQResponse>(
        `/stats/admin/drafts/participant-iq?phase=${phase}&min_seasons=${minSeasons}`,
      )
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [phase, minSeasons]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3 text-xs">
        <label className="text-vpv-text-muted">Fase</label>
        <select
          value={phase}
          onChange={(e) => setPhase(e.target.value as "preseason" | "winter")}
          className="rounded border border-vpv-border bg-vpv-bg px-2 py-1 text-vpv-text"
        >
          <option value="preseason">Pretemporada</option>
          <option value="winter">Invierno</option>
        </select>
        <label className="text-vpv-text-muted">Mínimo drafts</label>
        <select
          value={minSeasons}
          onChange={(e) => setMinSeasons(Number(e.target.value))}
          className="rounded border border-vpv-border bg-vpv-bg px-2 py-1 text-vpv-text"
        >
          {[1, 2, 3, 4].map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
      </div>

      {loading && (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-12 animate-pulse rounded-lg bg-vpv-border" />
          ))}
        </div>
      )}

      {!loading && data && data.participants.length === 0 && (
        <p className="rounded-lg border border-vpv-card-border bg-vpv-card p-4 text-sm text-vpv-text-muted">
          No hay participantes con al menos {minSeasons} drafts de fase «{phase}».
        </p>
      )}

      {!loading && data && data.participants.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-vpv-card-border bg-vpv-card">
          <table className="min-w-full text-xs">
            <thead className="border-b border-vpv-card-border bg-vpv-bg/40 text-vpv-text-muted">
              <tr>
                <th className="px-2 py-2 text-left">#</th>
                <th className="px-2 py-2 text-left">Participante</th>
                <th className="px-2 py-2 text-right" title="Cuántos drafts ha jugado">
                  Drafts
                </th>
                <th className="px-2 py-2 text-right" title="Total picks">
                  Picks
                </th>
                <th className="px-2 py-2 text-right" title="Media de Δ vs slot por pick">
                  Δ/pick
                </th>
                <th className="px-2 py-2 text-right" title="Suma de Δ vs slot">
                  Δ total
                </th>
                <th className="px-2 py-2 text-left">Mejor</th>
                <th className="px-2 py-2 text-left">Peor</th>
                <th className="px-2 py-2 text-center"></th>
              </tr>
            </thead>
            <tbody>
              {data.participants.map((p, idx) => (
                <>
                  <tr
                    key={p.display_name}
                    className="border-b border-vpv-card-border/40 last:border-0 hover:bg-vpv-bg/40"
                  >
                    <td className="px-2 py-1.5 font-mono text-vpv-text">{idx + 1}</td>
                    <td className="px-2 py-1.5 text-vpv-text">{p.display_name}</td>
                    <td className="px-2 py-1.5 text-right tabular-nums text-vpv-text-muted">
                      {p.n_drafts}
                    </td>
                    <td className="px-2 py-1.5 text-right tabular-nums text-vpv-text-muted">
                      {p.total_picks}
                    </td>
                    <td
                      className={`px-2 py-1.5 text-right tabular-nums font-bold ${
                        p.mean_delta_per_pick > 0
                          ? "text-emerald-400"
                          : p.mean_delta_per_pick < 0
                            ? "text-red-400"
                            : "text-vpv-text"
                      }`}
                    >
                      {p.mean_delta_per_pick > 0 ? "+" : ""}
                      {p.mean_delta_per_pick.toFixed(2)}
                    </td>
                    <td className="px-2 py-1.5 text-right tabular-nums text-vpv-text-muted">
                      {p.sum_delta_vs_slot > 0 ? "+" : ""}
                      {p.sum_delta_vs_slot}
                    </td>
                    <td className="px-2 py-1.5 text-emerald-300">
                      {p.best_pick
                        ? `${p.best_pick.player_name} (+${p.best_pick.delta_vs_slot}, ${p.best_pick.season_name} pick ${p.best_pick.pick_number})`
                        : "—"}
                    </td>
                    <td className="px-2 py-1.5 text-red-300">
                      {p.worst_pick
                        ? `${p.worst_pick.player_name} (${p.worst_pick.delta_vs_slot}, ${p.worst_pick.season_name} pick ${p.worst_pick.pick_number})`
                        : "—"}
                    </td>
                    <td className="px-2 py-1.5 text-center">
                      <button
                        onClick={() =>
                          setExpanded(
                            expanded === p.participant_id ? null : p.participant_id,
                          )
                        }
                        className="rounded px-1 py-0.5 text-[10px] text-vpv-text-muted hover:text-vpv-text"
                      >
                        {expanded === p.participant_id ? "▲" : "▼"}
                      </button>
                    </td>
                  </tr>
                  {expanded === p.participant_id && (
                    <tr key={`${p.display_name}-expanded`} className="bg-vpv-bg/30">
                      <td colSpan={9} className="px-3 py-2">
                        <p className="mb-1 text-[10px] uppercase tracking-wider text-vpv-text-muted">
                          Δ medio por ronda
                        </p>
                        <div className="flex flex-wrap gap-1">
                          {Object.entries(p.by_round).map(([round, delta]) => (
                            <span
                              key={round}
                              className={`rounded px-1.5 py-px text-[10px] font-bold ${
                                delta > 0
                                  ? "bg-emerald-500/15 text-emerald-300"
                                  : delta < 0
                                    ? "bg-red-500/15 text-red-300"
                                    : "bg-zinc-500/15 text-zinc-300"
                              }`}
                            >
                              R{round}: {delta > 0 ? "+" : ""}
                              {delta.toFixed(1)}
                            </span>
                          ))}
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
