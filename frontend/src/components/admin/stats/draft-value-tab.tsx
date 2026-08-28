"use client";

import { useState, useEffect, useMemo } from "react";
import { apiClient } from "@/lib/api-client";
import { sorted, SortDir, POS_COLOR } from "@/components/admin/stats/common";
import type {
  DraftValuePlayer,
  DraftValueResponse,
} from "@/types";

// Positional tier from the scorecard — instant context on how good a player is
// *for their position* (thresholds live in backend scorecard.py).
const TIER_BADGE: Record<string, { cls: string; label: string; title: string }> = {
  elite: { cls: "bg-green-500/20 text-green-300", label: "Elite", title: "Tier elite en su posición" },
  solid: { cls: "bg-blue-500/15 text-blue-300", label: "Sólido", title: "Tier sólido en su posición" },
  normal: { cls: "bg-vpv-bg text-vpv-text-muted", label: "Normal", title: "Tier normal en su posición" },
  weak: { cls: "bg-red-500/10 text-red-300", label: "Flojo", title: "Tier flojo en su posición" },
  team_dependent: { cls: "bg-amber-500/15 text-amber-300", label: "Equipo", title: "Portero: el valor depende del equipo (clean sheets), no de una escala de puntos" },
};

// Admin player tags (fixed set) — badges on the row + editable in the row.
// Effect on Priority lives in the backend (service_draft.TAG_MULTIPLIER).
const PLAYER_TAGS: { key: string; label: string; cls: string }[] = [
  { key: "titular", label: "Titular", cls: "bg-green-500/20 text-green-300" },
  { key: "suplente", label: "Suplente", cls: "bg-amber-500/15 text-amber-300" },
  { key: "penaltis", label: "Penaltis", cls: "bg-emerald-500/15 text-emerald-300" },
  { key: "lesion", label: "Lesión", cls: "bg-red-500/20 text-red-300" },
  { key: "objetivo", label: "Objetivo", cls: "bg-blue-500/20 text-blue-300" },
  { key: "evitar", label: "Evitar", cls: "bg-red-500/10 text-red-400" },
];
const TAG_LABEL: Record<string, string> = Object.fromEntries(
  PLAYER_TAGS.map((t) => [t.key, t.label]),
);
const TAG_CLS: Record<string, string> = Object.fromEntries(
  PLAYER_TAGS.map((t) => [t.key, t.cls]),
);

// Recommended roster composition (26 players), from the strategy analysis:
// forwards are the position most people under-draft (best formations play 3).
const ROSTER_TARGET: { pos: string; n: string; note: string }[] = [
  { pos: "POR", n: "2", note: "1 titular fijo de equipo con buena defensa" },
  { pos: "DEF", n: "8", note: "suelo alto; 3-4 titulares + fondo" },
  { pos: "MED", n: "7-8", note: "pool profundo y barato" },
  { pos: "DEL", n: "6-7", note: "fondo para poder alinear 3 siempre" },
];

/** Estimated draft round from the global VORP rank and the league size. */
function roundOf(p: DraftValuePlayer, participants: number): number | null {
  if (p.overall_rank == null || participants <= 0) return null;
  return Math.ceil(p.overall_rank / participants);
}

type DraftSortKey = keyof DraftValuePlayer;

// Order in which positional tiers sort (higher = better) when sorting by Tier.
const TIER_RANK: Record<string, number> = {
  elite: 5,
  solid: 4,
  normal: 3,
  team_dependent: 2,
  weak: 1,
};

// group: "core" columns always show (the draft-decision essentials, they fit on
// screen); "models" columns are the individual sub-model scores, hidden behind a
// toggle so the table isn't unusably wide. Every column stays sortable.
const DRAFT_COLS: { key: DraftSortKey; label: string; title: string; w: string; group: "core" | "models" }[] = [
  { key: "priority", label: "Prio", title: "Prioridad de draft (columna maestra), CON tus tags: puntos proyectados el resto de temporada, ajustados por riesgo (pico, banquillo, fiabilidad) y por los tags. Es el orden por defecto.", w: "w-16", group: "core" },
  { key: "priority_base", label: "Base", title: "Prioridad del MODELO, sin tus tags. Compárala con Prio: si difieren, es por tus etiquetas (Objetivo/Evitar/Lesión/…).", w: "w-16", group: "core" },
  { key: "vorp", label: "VORP", title: "Valor sobre reemplazo posicional: valor efectivo por encima del jugador de reemplazo en su posición. Compara DEF/MED/DEL/POR en un solo eje. Diagnóstico de escasez.", w: "w-14", group: "core" },
  { key: "effective_value", label: "Efect", title: "Valor efectivo usado para el ranking = valor manual si lo has puesto, si no la proyección automática.", w: "w-14", group: "core" },
  { key: "manual_value", label: "Manual", title: "Tu valor manual (pts/partido). Sobrescribe la proyección. Edítalo abriendo la fila. Imprescindible para jugadores nuevos sin histórico.", w: "w-14", group: "core" },
  { key: "proj_rest_points", label: "PtsRes", title: "Puntos proyectados resto de temporada = valor efectivo × partidos esperados restantes (jornadas restantes × disponibilidad).", w: "w-16", group: "core" },
  { key: "event_share", label: "Fiab", title: "Fiabilidad: % de puntos por eventos concretos (goles, asistencias, portería a cero...) vs nota mediática Marca/AS. Alto = más repetible.", w: "w-12", group: "core" },
  { key: "team_goals_conceded", label: "DefEq", title: "Defensa del equipo: goles que encaja por partido (temporada pasada; prior neutro para ascendidos). Menos = mejor. El factor clave para porteros (corr −0.83 con sus puntos).", w: "w-14", group: "core" },
  { key: "ensemble_score", label: "Ens", title: "Ensemble: valor proyectado (histórico + actual, shrinkage k=4)", w: "w-14", group: "models" },
  { key: "simple_avg", label: "Avg", title: "Media simple: pts/partido temporada anterior (baseline)", w: "w-14", group: "models" },
  { key: "second_half_score", label: "Form", title: "Forma 2a mitad: rendimiento J20-J38 (predice siguiente temporada)", w: "w-14", group: "models" },
  { key: "stability_score", label: "Stab", title: "Estabilidad: minutos altos y constantes (menor riesgo busto)", w: "w-14", group: "models" },
  { key: "productivity_score", label: "Prod", title: "Productividad: bonificado por G+A por 90 minutos", w: "w-14", group: "models" },
  { key: "career_trend_pct", label: "Trend", title: "Tendencia interanual: % mejora o declive", w: "w-14", group: "models" },
  { key: "availability", label: "Disp", title: "Disponibilidad: % partidos con 45+ min jugados", w: "w-12", group: "models" },
  { key: "consistency", label: "Cons", title: "Consistencia: 1-CV (1=muy fiable, 0=impredecible)", w: "w-12", group: "models" },
];

function ManualOverrideEditor({
  seasonId,
  player,
  onSaved,
}: {
  seasonId: number;
  player: DraftValuePlayer;
  onSaved: (resp: DraftValueResponse) => void;
}) {
  const [value, setValue] = useState(
    player.manual_value != null ? String(player.manual_value) : "",
  );
  const [note, setNote] = useState(player.note ?? "");
  const [tags, setTags] = useState<string[]>(player.tags ?? []);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const toggleTag = (k: string) =>
    setTags((t) => (t.includes(k) ? t.filter((x) => x !== k) : [...t, k]));

  async function save() {
    const trimmed = value.trim();
    const manual_value = trimmed === "" ? null : Number(trimmed);
    if (manual_value != null && !Number.isFinite(manual_value)) {
      setErr("Valor inválido");
      return;
    }
    setSaving(true);
    setErr(null);
    try {
      const resp = await apiClient.put<DraftValueResponse>(
        `/stats/admin/${seasonId}/draft-value/${player.player_id}/override`,
        { manual_value, note: note.trim() || null, tags },
      );
      onSaved(resp);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Error guardando");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mt-3 flex flex-wrap items-end gap-2 border-t border-vpv-border/30 pt-2">
      <div className="flex w-full flex-wrap items-center gap-1.5">
        <span className="text-[10px] text-vpv-text-muted">Tags:</span>
        {PLAYER_TAGS.map((t) => {
          const on = tags.includes(t.key);
          return (
            <button
              key={t.key}
              type="button"
              onClick={() => toggleTag(t.key)}
              className={`rounded px-1.5 py-0.5 text-[10px] font-medium transition ${
                on ? t.cls : "border border-vpv-border text-vpv-text-muted hover:text-vpv-text"
              }`}
            >
              {t.label}
            </button>
          );
        })}
        <span className="text-[9px] text-vpv-text-muted">ajustan la Prioridad</span>
      </div>
      <label className="text-[10px] text-vpv-text-muted">
        Valor manual (pts/partido)
        <input
          type="number"
          step="0.1"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={player.auto_projection != null ? `auto ${player.auto_projection}` : "—"}
          className="mt-0.5 block w-28 rounded border border-vpv-border bg-vpv-bg px-2 py-1 text-xs text-vpv-text"
        />
      </label>
      <label className="flex-1 text-[10px] text-vpv-text-muted">
        Nota
        <input
          type="text"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="p.ej. fichaje estrella / rol nuevo / lesión"
          className="mt-0.5 block w-full rounded border border-vpv-border bg-vpv-bg px-2 py-1 text-xs text-vpv-text"
        />
      </label>
      <button
        onClick={save}
        disabled={saving}
        className="rounded bg-vpv-accent px-3 py-1.5 text-xs font-medium text-vpv-bg transition-opacity disabled:opacity-40"
      >
        {saving ? "Guardando…" : "Guardar"}
      </button>
      {err && <span className="text-[10px] text-red-400">{err}</span>}
      <span className="text-[10px] text-vpv-text-muted">
        Vacío → usa la proyección automática.
      </span>
    </div>
  );
}

export function DraftValueTab({ seasonId }: { seasonId: number }) {
  const [data, setData] = useState<DraftValueResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [posFilter, setPosFilter] = useState("");
  const [sortKey, setSortKey] = useState<DraftSortKey>("priority");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [error, setError] = useState(false);
  const [showAll, setShowAll] = useState(false);
  // Column groups: keep the essential columns on screen; reveal the individual
  // model scores on demand so the table isn't unusably wide.
  const [showModels, setShowModels] = useState(false);
  const visibleCols = useMemo(
    () => (showModels ? DRAFT_COLS : DRAFT_COLS.filter((c) => c.group === "core")),
    [showModels],
  );
  // Table needs a wider min-width when the model columns are shown so nothing
  // cramps; narrower otherwise so the core view fits without scrolling.
  const tableMinW = showModels ? "md:min-w-[1450px]" : "md:min-w-[1024px]";

  const handleSort = (key: DraftSortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      // Ronda and team goals conceded are "lower is better" → default ascending.
      setSortDir(key === "overall_rank" || key === "team_goals_conceded" ? "asc" : "desc");
    }
  };

  useEffect(() => {
    let cancelled = false;
    apiClient
      .get<DraftValueResponse>(`/stats/${seasonId}/players/draft-value`)
      .then((d) => {
        if (!cancelled) { setData(d); setError(false); }
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [seasonId]);

  const players = useMemo(() => {
    if (!data) return [];
    let list = data.players;
    if (posFilter) list = list.filter((p) => p.position === posFilter);
    // Tier is categorical — sort by its quality rank, not alphabetically.
    if (sortKey === "position_tier") {
      const dir = sortDir === "asc" ? 1 : -1;
      return [...list].sort(
        (a, b) =>
          dir *
          ((TIER_RANK[a.position_tier ?? ""] ?? 0) -
            (TIER_RANK[b.position_tier ?? ""] ?? 0)),
      );
    }
    return sorted(list, sortKey, sortDir);
  }, [data, posFilter, sortKey, sortDir]);

  // Positional scarcity: how deep the draftable pool runs per position.
  // Fewer players above replacement (vorp > 0) => scarcer => draft earlier.
  const scarcity = useMemo(() => {
    if (!data) return [];
    return (["POR", "DEF", "MED", "DEL"] as const).map((pos) => {
      const inPos = data.players.filter(
        (p) => p.position === pos && p.vorp != null,
      );
      const aboveRepl = inPos.filter((p) => (p.vorp ?? 0) > 0).length;
      const topVorp = inPos.reduce((m, p) => Math.max(m, p.vorp ?? 0), 0);
      return { pos, total: inPos.length, aboveRepl, topVorp };
    });
  }, [data]);

  if (loading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="h-10 animate-pulse rounded bg-vpv-border" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
        Error al cargar datos de draft.{" "}
        <button onClick={() => { setLoading(true); setError(false); }} className="underline">
          Reintentar
        </button>
      </div>
    );
  }

  if (!data) return <p className="text-sm text-vpv-text-muted">Sin datos</p>;

  return (
    <div className="space-y-3">
      {/* Header info */}
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card px-4 py-2.5">
        <div className="flex flex-wrap items-center gap-3 text-xs text-vpv-text-muted">
          <span>
            <b className="text-vpv-text">{data.draft_type === "winter" ? "Draft Invierno" : "Draft Pretemporada"}</b>
            {" "}{data.season_name}
          </span>
          <span>J{data.matchdays_played} jugadas</span>
          <span>Peso historial: {(data.peso_historico * 100).toFixed(0)}%</span>
          <span>{players.length} jugadores</span>
        </div>
      </div>

      {/* Positional scarcity — draft the shallow positions earlier */}
      {scarcity.some((s) => s.total > 0) && (
        <div className="rounded-lg border border-vpv-card-border bg-vpv-card px-4 py-2.5">
          <div className="mb-1.5 flex items-baseline gap-2">
            <h4 className="text-xs font-semibold text-vpv-text">
              Escasez por posicion
            </h4>
            <span className="text-[10px] text-vpv-text-muted">
              jugadores por encima del reemplazo (VORP &gt; 0) — cuantos menos, antes conviene draftear
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {scarcity.map((s) => (
              <button
                key={s.pos}
                type="button"
                onClick={() => setPosFilter(posFilter === s.pos ? "" : s.pos)}
                className={`rounded-lg border px-3 py-2 text-left transition ${
                  posFilter === s.pos
                    ? "border-vpv-accent bg-vpv-accent/10"
                    : "border-vpv-border bg-vpv-bg hover:border-vpv-accent/50"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span
                    className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${POS_COLOR[s.pos] ?? "bg-vpv-bg text-vpv-text-muted"}`}
                  >
                    {s.pos}
                  </span>
                  <span className="text-lg font-bold text-vpv-accent">
                    {s.aboveRepl}
                  </span>
                </div>
                <p className="mt-1 text-[10px] text-vpv-text-muted">
                  {s.total} drafteables · techo VORP {s.topVorp.toFixed(1)}
                </p>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Roster target — reference composition + best formations */}
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card px-4 py-2.5">
        <div className="mb-1.5 flex flex-wrap items-baseline gap-2">
          <h4 className="text-xs font-semibold text-vpv-text">Objetivo de plantilla (26)</h4>
          <span className="text-[10px] text-vpv-text-muted">
            reparto recomendado por datos — el delantero suele infra-draftearse
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {ROSTER_TARGET.map((r) => (
            <div
              key={r.pos}
              className="flex items-center gap-1.5 rounded border border-vpv-border bg-vpv-bg px-2 py-1"
              title={r.note}
            >
              <span className={`rounded px-1 py-0.5 text-[9px] font-medium ${POS_COLOR[r.pos] ?? ""}`}>
                {r.pos}
              </span>
              <span className="text-sm font-bold tabular-nums text-vpv-text">{r.n}</span>
            </div>
          ))}
          <span className="ml-1 text-[10px] text-vpv-text-muted">
            Formación: <b className="text-vpv-text">1-4-3-3</b> / <b className="text-vpv-text">1-3-4-3</b> (3 delanteros)
          </span>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-end gap-2">
        <div className="flex gap-0.5">
          {["", "POR", "DEF", "MED", "DEL"].map((p) => (
            <button
              key={p}
              onClick={() => setPosFilter(p)}
              className={`rounded px-2 py-1 text-[10px] font-medium ${
                posFilter === p ? "bg-vpv-accent text-white" : "border border-vpv-border text-vpv-text-muted"
              }`}
            >
              {p || "Todas"}
            </button>
          ))}
        </div>
        <button
          onClick={() => setShowModels((v) => !v)}
          title="Muestra u oculta las columnas de sub-modelos (Ens, Avg, Form, Stab, Prod, Trend, Disp, Cons). Siguen siendo ordenables."
          className={`rounded px-2 py-1 text-[10px] font-medium transition ${
            showModels ? "bg-vpv-accent text-white" : "border border-vpv-border text-vpv-text-muted hover:text-vpv-text"
          }`}
        >
          {showModels ? "− Modelos" : "+ Modelos"}
        </button>
        <span className="text-[10px] text-vpv-text-muted">Click columna para ordenar</span>
      </div>

      {/* Table */}
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
       <div className="overflow-x-auto">
        {/* Desktop header */}
        <div className={`hidden ${tableMinW} border-b border-vpv-border bg-vpv-bg px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-vpv-text-muted md:flex`}>
          <span className="w-8 shrink-0">#</span>
          <span className="w-52 shrink-0">Jugador</span>
          <span className="w-32 shrink-0" title="Alertas: nuevo, cambio de equipo/posición, pico de forma, penaltis, riesgo banquillo">Alertas</span>
          <span className="w-10 shrink-0 text-center">Pos</span>
          <button
            onClick={() => handleSort("position_tier")}
            title="Tier posicional (elite / sólido / normal / flojo; los porteros dependen del equipo)"
            className={`w-16 shrink-0 text-center hover:text-vpv-text ${sortKey === "position_tier" ? "text-vpv-accent" : ""}`}
          >
            Tier
            {sortKey === "position_tier" && (
              <span className="ml-0.5">{sortDir === "desc" ? "▼" : "▲"}</span>
            )}
          </button>
          <button
            onClick={() => handleSort("overall_rank")}
            title="Ronda estimada de draft = rank VORP global ÷ nº de participantes"
            className={`w-12 shrink-0 text-center hover:text-vpv-text ${sortKey === "overall_rank" ? "text-vpv-accent" : ""}`}
          >
            Ronda
            {sortKey === "overall_rank" && (
              <span className="ml-0.5">{sortDir === "desc" ? "▼" : "▲"}</span>
            )}
          </button>
          {visibleCols.map((col) => (
            <button
              key={col.key}
              onClick={() => handleSort(col.key)}
              title={col.title}
              className={`${col.w} shrink-0 text-right hover:text-vpv-text ${sortKey === col.key ? "text-vpv-accent" : ""}`}
            >
              {col.label}
              {sortKey === col.key && (
                <span className="ml-0.5">{sortDir === "desc" ? "\u25BC" : "\u25B2"}</span>
              )}
            </button>
          ))}
        </div>

        {data.players.length === 0 && (
          <div className="rounded-lg border border-vpv-card-border bg-vpv-card px-4 py-6 text-center text-sm text-vpv-text-muted">
            Aún no hay jugadores drafteables. Importa equipos y plantillas de la
            temporada (Admin → Temporadas → Scrapear) y el tablero se llenará con
            las proyecciones desde el histórico.
          </div>
        )}
        <div className="divide-y divide-vpv-border/50">
          {(showAll ? players : players.slice(0, 100)).map((p, i) => {
            const tier = p.position_tier ? TIER_BADGE[p.position_tier] : null;
            const rnd = roundOf(p, data.participant_count);
            const isExpanded = expandedId === p.player_id;

            return (
              <div key={p.player_id}>
                <button
                  type="button"
                  onClick={() => setExpandedId(isExpanded ? null : p.player_id)}
                  className={`flex w-full items-center px-3 py-1.5 text-left hover:bg-vpv-bg/30 ${tableMinW} ${isExpanded ? "bg-vpv-bg/40" : ""}`}
                >
                  {/* Mobile: compact */}
                  <div className="flex flex-1 items-center gap-2 md:hidden">
                    <span className="w-6 text-[10px] text-vpv-text-muted">{i + 1}</span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-xs font-medium text-vpv-text">
                        {p.display_name}
                        {tier && (
                          <span className={`ml-1 rounded px-1 py-0.5 text-[8px] font-medium ${tier.cls}`}>{tier.label}</span>
                        )}
                      </p>
                      <p className="text-[10px] text-vpv-text-muted">
                        {p.team_name} · {p.position}
                        {rnd != null && <span className="ml-1 text-vpv-accent">· R{rnd}</span>}
                      </p>
                    </div>
                    <span className="text-right text-[9px] leading-tight text-vpv-text-muted">
                      Prio
                      <span className="block text-xs font-bold tabular-nums text-vpv-accent">
                        {p.priority != null ? p.priority.toFixed(0) : "—"}
                      </span>
                    </span>
                  </div>

                  {/* Desktop: full row */}
                  <div className={`hidden ${tableMinW} items-center md:flex`}>
                    <span className="w-8 shrink-0 text-[10px] text-vpv-text-muted">{i + 1}</span>
                    <span className="w-52 shrink-0 truncate text-xs font-medium text-vpv-text">
                      {p.display_name}
                      <span className="ml-1 text-[10px] font-normal text-vpv-text-muted">{p.team_name}</span>
                    </span>
                    <span className="flex w-32 shrink-0 items-center gap-0.5 overflow-hidden">
                      {p.is_new && (
                        <span className="rounded bg-amber-500/15 px-1 text-[8px] text-amber-400">NUEVO</span>
                      )}
                      {p.team_changed && (
                        <span className="rounded bg-blue-500/15 px-1 text-[8px] text-blue-300" title="Cambió de equipo">+EQ</span>
                      )}
                      {p.position_changed && (
                        <span className="rounded bg-purple-500/15 px-1 text-[8px] text-purple-300" title="Cambió de posición">+POS</span>
                      )}
                      {p.is_peak_year && (
                        <span className="rounded bg-orange-500/15 px-1 text-[8px] text-orange-300" title="Pico de forma: última temporada muy por encima de su media — riesgo de regresión">PICO</span>
                      )}
                      {p.is_penalty_taker && (
                        <span className="rounded bg-emerald-500/15 px-1 text-[8px] text-emerald-300" title="Lanzó penaltis la temporada pasada (bonus de techo; verifica el lanzador actual)">PEN</span>
                      )}
                      {p.is_bench_risk && (
                        <span className="rounded bg-red-500/15 px-1 text-[8px] text-red-300" title="Riesgo de banquillo: rota o juega pocos partidos">🪑</span>
                      )}
                      {p.tags?.map((t) => (
                        <span key={t} className={`rounded px-1 text-[8px] ${TAG_CLS[t] ?? "bg-vpv-bg text-vpv-text-muted"}`} title="Tag admin (ajusta Prioridad)">
                          {TAG_LABEL[t] ?? t}
                        </span>
                      ))}
                    </span>
                    <span className="w-10 shrink-0 text-center text-[10px] text-vpv-text-muted">{p.position}</span>
                    <span className="w-16 shrink-0 text-center">
                      {tier ? (
                        <span className={`rounded px-1 py-0.5 text-[9px] font-medium ${tier.cls}`} title={tier.title}>
                          {tier.label}
                        </span>
                      ) : (
                        <span className="text-[10px] text-vpv-text-muted">—</span>
                      )}
                    </span>
                    <span
                      className="w-12 shrink-0 text-center text-[10px] tabular-nums text-vpv-text-muted"
                      title={p.overall_rank != null ? `Pick global #${p.overall_rank}` : undefined}
                    >
                      {rnd != null ? `R${rnd}` : p.overall_rank != null ? `#${p.overall_rank}` : "—"}
                    </span>
                    {visibleCols.map((col) => {
                      const val = p[col.key];
                      const isActive = sortKey === col.key;
                      if (col.key === "career_trend_pct") {
                        return (
                          <span key={col.key} className={`${col.w} shrink-0 text-right text-xs tabular-nums ${
                            val != null && (val as number) > 0.05 ? "text-green-400" :
                            val != null && (val as number) < -0.05 ? "text-red-400" : "text-vpv-text-muted"
                          } ${isActive ? "font-bold" : ""}`}>
                            {val != null ? `${(val as number) > 0 ? "+" : ""}${((val as number) * 100).toFixed(0)}%` : "—"}
                          </span>
                        );
                      }
                      if (col.key === "availability" || col.key === "consistency" || col.key === "event_share") {
                        const n = (val as number) ?? 0;
                        return (
                          <span key={col.key} className={`${col.w} shrink-0 text-right text-xs tabular-nums ${isActive ? "font-bold text-vpv-accent" : "text-vpv-text-muted"}`}>
                            {(n * 100).toFixed(0)}%
                          </span>
                        );
                      }
                      if (col.key === "team_goals_conceded") {
                        // Fewer goals conceded = stronger defense = greener.
                        return (
                          <span key={col.key} className={`${col.w} shrink-0 text-right text-xs tabular-nums ${
                            val != null && (val as number) < 1.1 ? "text-green-400" :
                            val != null && (val as number) > 1.4 ? "text-red-400" : "text-vpv-text-muted"
                          } ${isActive ? "font-bold" : ""}`}>
                            {val != null ? (val as number).toFixed(1) : "—"}
                          </span>
                        );
                      }
                      return (
                        <span key={col.key} className={`${col.w} shrink-0 text-right text-xs tabular-nums ${
                          isActive ? "font-bold text-vpv-accent" : col.key === "ensemble_score" ? "font-bold text-vpv-accent" : "text-vpv-text-muted"
                        }`}>
                          {val != null ? (val as number).toFixed(1) : "—"}
                        </span>
                      );
                    })}
                  </div>
                </button>

                {/* Expanded detail */}
                {isExpanded && (
                  <div className="border-t border-vpv-border/30 bg-vpv-bg/20 px-4 py-2.5 text-xs">
                    <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 sm:grid-cols-3 md:grid-cols-4">
                      <div>
                        <span className="text-vpv-text-muted">Temporadas: </span>
                        <span className="font-medium text-vpv-text">{p.seasons_played}</span>
                      </div>
                      <div>
                        <span className="text-vpv-text-muted">Partidos: </span>
                        <span className="font-medium text-vpv-text">{p.games_played}</span>
                      </div>
                      <div>
                        <span className="text-vpv-text-muted">Pts totales: </span>
                        <span className="font-medium text-vpv-text">{p.total_points.toFixed(0)}</span>
                      </div>
                      <div>
                        <span className="text-vpv-text-muted">Disponibilidad: </span>
                        <span className={`font-medium ${p.availability > 0.8 ? "text-green-400" : p.availability > 0.6 ? "text-amber-400" : "text-red-400"}`}>
                          {(p.availability * 100).toFixed(0)}%
                        </span>
                      </div>
                      <div>
                        <span className="text-vpv-text-muted">Goles: </span>
                        <span className="font-medium text-vpv-text">{p.goals}</span>
                      </div>
                      <div>
                        <span className="text-vpv-text-muted">Asistencias: </span>
                        <span className="font-medium text-vpv-text">{p.assists}</span>
                      </div>
                      {p.marca_avg != null && (
                        <div>
                          <span className="text-vpv-text-muted">Marca: </span>
                          <span className="font-medium text-vpv-text">{p.marca_avg.toFixed(1)} estrellas</span>
                        </div>
                      )}
                      {p.as_avg != null && (
                        <div>
                          <span className="text-vpv-text-muted">AS: </span>
                          <span className="font-medium text-vpv-text">{p.as_avg.toFixed(1)} picas</span>
                        </div>
                      )}
                      {p.second_half_avg != null && (
                        <div>
                          <span className="text-vpv-text-muted">2a mitad: </span>
                          <span className="font-medium text-vpv-text">{p.second_half_avg.toFixed(1)} pts/j</span>
                        </div>
                      )}
                      <div>
                        <span className="text-vpv-text-muted">Productividad: </span>
                        <span className="font-medium text-vpv-text">{p.productivity_score.toFixed(1)}</span>
                      </div>
                    </div>
                    <ManualOverrideEditor seasonId={seasonId} player={p} onSaved={setData} />
                  </div>
                )}
              </div>
            );
          })}
        </div>
       </div>
      </div>

      {!showAll && players.length > 100 && (
        <button
          onClick={() => setShowAll(true)}
          className="w-full rounded-lg border border-vpv-border py-2 text-xs text-vpv-text-muted hover:text-vpv-text"
        >
          Mostrando 100 de {players.length} — Ver todos
        </button>
      )}

      {/* Model legend */}
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card px-4 py-2.5">
        <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-vpv-text-muted">Modelos (backtested)</p>
        <div className="grid grid-cols-1 gap-1 text-[10px] sm:grid-cols-2">
          {data.model_info && Object.entries(data.model_info).map(([key, desc]) => (
            <div key={key}>
              <span className="font-medium text-vpv-text">{key}: </span>
              <span className="text-vpv-text-muted">{desc}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
