/**
 * Admin Statistics Page — /admin/estadisticas
 *
 * Orchestrator: season selector + tab bar + per-tab lazy fetch. Each tab is a
 * self-contained component under `components/admin/stats/`:
 *  - Jugadores    -> PlayersTab        (GET /stats/{id}/players)
 *  - Participantes -> ParticipantsTab  (GET /stats/{id}/participants)
 *  - Liga         -> LeagueTab         (GET /stats/{id}/league)
 *  - Avanzado     -> AdvancedTab / ContextoTab (players/advanced, teams/dependency)
 *  - Draft Valor  -> DraftValueTab     (players/draft-value)
 *  - Draft Retro  -> DraftRetroTab
 *  - Guía         -> StatsGuide
 */
"use client";

import { useCallback, useEffect, useState } from "react";
import { apiClient } from "@/lib/api-client";
import { DraftRetroTab } from "@/components/admin/draft-retro-tab";
import { StatsGuide } from "@/components/admin/stats-guide";
import { PlayersTab } from "@/components/admin/stats/players-tab";
import { ParticipantsTab } from "@/components/admin/stats/participants-tab";
import { LeagueTab } from "@/components/admin/stats/league-tab";
import { AdvancedTab } from "@/components/admin/stats/advanced-tab";
import { ContextoTab } from "@/components/admin/stats/contexto-tab";
import { DraftValueTab } from "@/components/admin/stats/draft-value-tab";
import type {
  PlayerStatRow,
  PlayerStatsResponse,
  ParticipantBreakdown,
  ParticipantExtremes,
  ParticipantStatsResponse,
  FormationUsage,
  MatchdayAverageEntry,
  RecordEntry,
  LeagueStatsResponse,
  AdvancedPlayerStat,
  AdvancedPlayersResponse,
  TeamDependencyEntry,
  TeamDependencyResponse,
} from "@/types";

// ---------------------------------------------------------------------------
// Sub-tabs
// ---------------------------------------------------------------------------

// Top-level tabs grouped by *use* (see docs / plan): the draft board, the
// performance browser (several lenses over the same data), draft analysis,
// and the metrics guide. Weekly xPts lives in its own page (/admin/predicciones).
const MAIN_TABS = [
  { key: "draft", label: "Draft" },
  { key: "rendimiento", label: "Rendimiento" },
  { key: "analisis", label: "Análisis" },
  { key: "guia", label: "📖 Guía" },
] as const;

type MainTab = (typeof MAIN_TABS)[number]["key"];

// Lenses inside "Rendimiento" — same job (understand performance), different cut.
const PERF_LENSES = [
  { key: "jugadores", label: "Jugadores" },
  { key: "participantes", label: "Participantes" },
  { key: "liga", label: "Liga" },
  { key: "avanzado", label: "Avanzado" },
  { key: "contexto", label: "Contexto" },
] as const;

type PerfLens = (typeof PERF_LENSES)[number]["key"];

interface SeasonOption {
  id: number;
  name: string;
  status: string;
}

/** Position badge colors — consistent with other admin tables. */

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3">
      <p className="text-sm text-red-400">{message}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Player Stats Tab
// ---------------------------------------------------------------------------


export default function AdminEstadisticasPage() {
  const [seasons, setSeasons] = useState<SeasonOption[]>([]);
  const [selectedSeasonId, setSelectedSeasonId] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<MainTab>("rendimiento");
  const [perfLens, setPerfLens] = useState<PerfLens>("jugadores");
  const [includeNoncounting, setIncludeNoncounting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Data per tab
  const [players, setPlayers] = useState<PlayerStatRow[]>([]);
  const [breakdowns, setBreakdowns] = useState<ParticipantBreakdown[]>([]);
  const [extremes, setExtremes] = useState<ParticipantExtremes[]>([]);
  const [formations, setFormations] = useState<FormationUsage[]>([]);
  const [matchdayAverages, setMatchdayAverages] = useState<
    MatchdayAverageEntry[]
  >([]);
  const [records, setRecords] = useState<RecordEntry[]>([]);
  const [advancedPlayers, setAdvancedPlayers] = useState<AdvancedPlayerStat[]>(
    [],
  );
  const [dependencyData, setDependencyData] = useState<TeamDependencyEntry[]>([]);
  const [tabLoading, setTabLoading] = useState(false);

  const fetchSeasons = useCallback(async () => {
    try {
      const data = await apiClient.get<SeasonOption[]>("/seasons");
      setSeasons(data);
      if (data.length > 0 && selectedSeasonId === null) {
        const active = data.find((s) => s.status === "active") ?? data[0];
        setSelectedSeasonId(active.id);
      }
    } catch (err) {
      setError(
        `Error al cargar temporadas: ${err instanceof Error ? err.message : "desconocido"}`,
      );
    } finally {
      setLoading(false);
    }
  }, [selectedSeasonId]);

  useEffect(() => {
    fetchSeasons();
  }, [fetchSeasons]);

  // Only the "Rendimiento" lenses need a page-level fetch; Draft/Análisis
  // self-fetch inside their components and Guía is static.
  const fetchLensData = useCallback(
    async (lens: PerfLens, seasonId: number) => {
      setTabLoading(true);
      setError(null);
      try {
        if (lens === "jugadores") {
          const data = await apiClient.get<PlayerStatsResponse>(
            `/stats/${seasonId}/players${includeNoncounting ? "?include_noncounting=true" : ""}`,
          );
          setPlayers(data.players);
        } else if (lens === "participantes") {
          const data = await apiClient.get<ParticipantStatsResponse>(
            `/stats/${seasonId}/participants`,
          );
          setBreakdowns(data.breakdowns);
          setExtremes(data.extremes);
        } else if (lens === "liga") {
          const data = await apiClient.get<LeagueStatsResponse>(
            `/stats/${seasonId}/league`,
          );
          setFormations(data.formations);
          setMatchdayAverages(data.matchday_averages);
          setRecords(data.records);
        } else if (lens === "avanzado" || lens === "contexto") {
          const q = includeNoncounting ? "?include_noncounting=true" : "";
          const [advData, depData] = await Promise.all([
            apiClient.get<AdvancedPlayersResponse>(
              `/stats/${seasonId}/players/advanced${q}`,
            ),
            apiClient.get<TeamDependencyResponse>(
              `/stats/${seasonId}/teams/dependency${q}`,
            ),
          ]);
          setAdvancedPlayers(advData.players);
          setDependencyData(depData.entries);
        }
      } catch (err) {
        setError(
          `Error al cargar ${lens}: ${err instanceof Error ? err.message : "desconocido"}`,
        );
      } finally {
        setTabLoading(false);
      }
    },
    [includeNoncounting],
  );

  useEffect(() => {
    if (selectedSeasonId !== null && activeTab === "rendimiento") {
      fetchLensData(perfLens, selectedSeasonId);
    }
  }, [selectedSeasonId, activeTab, perfLens, fetchLensData]);

  if (loading) {
    return (
      <div className="space-y-2 py-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <div
            key={i}
            className="h-12 animate-pulse rounded-lg bg-vpv-border"
          />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-sm text-vpv-text-muted">Temporada:</label>
        <select
          value={selectedSeasonId ?? ""}
          onChange={(e) => setSelectedSeasonId(Number(e.target.value))}
          className="rounded border border-vpv-border bg-vpv-bg px-3 py-1.5 text-sm text-vpv-text"
        >
          {seasons.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </div>

      {/* Error */}
      {error && <ErrorBanner message={error} />}

      {/* Top tabs (by use) */}
      <div className="flex gap-1 border-b border-vpv-border pb-px">
        {MAIN_TABS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`rounded-t-md px-3 py-2 text-sm font-medium transition-colors ${
              activeTab === key
                ? "border-b-2 border-vpv-accent text-vpv-accent"
                : "text-vpv-text-muted hover:text-vpv-text"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Draft */}
      {activeTab === "draft" && selectedSeasonId && (
        <DraftValueTab seasonId={selectedSeasonId} />
      )}

      {/* Análisis */}
      {activeTab === "analisis" && (
        <DraftRetroTab seasons={seasons} defaultSeasonId={selectedSeasonId} />
      )}

      {/* Guía */}
      {activeTab === "guia" && <StatsGuide />}

      {/* Rendimiento — several lenses over the same performance data */}
      {activeTab === "rendimiento" && (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-1">
            {PERF_LENSES.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setPerfLens(key)}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                  perfLens === key
                    ? "bg-vpv-accent text-white"
                    : "bg-vpv-card text-vpv-text-muted hover:text-vpv-text"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Pre-draft toggle: applies to the player-centric lenses whose
              queries filter counts=true (Jugadores / Avanzado / Contexto). */}
          {(["jugadores", "avanzado", "contexto"] as PerfLens[]).includes(
            perfLens,
          ) && (
            <label className="flex items-center gap-2 text-xs text-vpv-text-muted">
              <input
                type="checkbox"
                checked={includeNoncounting}
                onChange={(e) => setIncludeNoncounting(e.target.checked)}
                className="accent-vpv-accent"
              />
              Incluir jornadas pre-draft / no computables (para preparar el draft
              antes de que la liga empiece a contar)
            </label>
          )}

          {tabLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <div
                  key={i}
                  className="h-10 animate-pulse rounded-lg bg-vpv-border"
                />
              ))}
            </div>
          ) : (
            <>
              {perfLens === "jugadores" && <PlayersTab players={players} />}
              {perfLens === "participantes" && (
                <ParticipantsTab breakdowns={breakdowns} extremes={extremes} />
              )}
              {perfLens === "liga" && (
                <LeagueTab
                  formations={formations}
                  matchdayAverages={matchdayAverages}
                  records={records}
                />
              )}
              {perfLens === "avanzado" && (
                <AdvancedTab players={advancedPlayers} />
              )}
              {perfLens === "contexto" && selectedSeasonId && (
                <ContextoTab
                  seasonId={selectedSeasonId}
                  dependency={dependencyData}
                  advancedPlayers={advancedPlayers}
                  includeNoncounting={includeNoncounting}
                />
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
