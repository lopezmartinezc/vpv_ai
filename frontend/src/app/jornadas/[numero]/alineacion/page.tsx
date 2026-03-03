"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import { apiClient, ApiClientError } from "@/lib/api-client";
import { PlayerAvatar } from "@/components/ui/player-avatar";
import { PitchView } from "@/components/ui/pitch-view";
import type { PitchPlayer } from "@/components/ui/pitch-view";
import { SkeletonTable } from "@/components/ui/skeleton";
import type {
  MatchdayDetailResponse,
  MatchEntry,
  MyLineupResponse,
  SquadPlayerEntry,
  ValidFormation,
} from "@/types";

// ---------------------------------------------------------------------------
// Types & Constants
// ---------------------------------------------------------------------------

interface LineupSubmitBody {
  formation: string;
  players: { player_id: number; position_slot: string }[];
}

const POSITION_ORDER = ["POR", "DEF", "MED", "DEL"] as const;
type Position = (typeof POSITION_ORDER)[number];

const POSITION_LABELS: Record<Position, string> = {
  POR: "Porteros",
  DEF: "Defensas",
  MED: "Centrocampistas",
  DEL: "Delanteros",
};

const POSITION_COLORS: Record<Position, string> = {
  POR: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  DEF: "bg-blue-500/15 text-blue-400 border-blue-500/30",
  MED: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  DEL: "bg-rose-500/15 text-rose-400 border-rose-500/30",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function countsByPosition(
  selected: SquadPlayerEntry[],
): Record<Position, number> {
  return {
    POR: selected.filter((p) => p.position === "POR").length,
    DEF: selected.filter((p) => p.position === "DEF").length,
    MED: selected.filter((p) => p.position === "MED").length,
    DEL: selected.filter((p) => p.position === "DEL").length,
  };
}

function minutesUntil(isoDate: string | null): number | null {
  if (!isoDate) return null;
  const diff = new Date(isoDate).getTime() - Date.now();
  return diff > 0 ? Math.floor(diff / 60_000) : null;
}

function formatMatchTime(playedAt: string | null): string {
  if (!playedAt) return "";
  const d = new Date(playedAt);
  const day = d.toLocaleDateString("es-ES", { weekday: "short" });
  const time = d.toLocaleTimeString("es-ES", {
    hour: "2-digit",
    minute: "2-digit",
  });
  return `${day} ${time}`;
}

/** Check if a player of the given position can be added without making it
 *  impossible to reach any valid formation. */
function canAddToPosition(
  pos: Position,
  counts: Record<Position, number>,
  formations: ValidFormation[],
  total: number,
): boolean {
  if (total >= 11) return false;
  if (pos === "POR") return counts.POR < 1;
  const next = { ...counts, [pos]: counts[pos] + 1 };
  return formations.some(
    (f) =>
      next.DEF <= f.defenders &&
      next.MED <= f.midfielders &&
      next.DEL <= f.forwards,
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function DeadlineBanner({
  firstMatchAt,
  deadlineMin,
}: {
  firstMatchAt: string | null;
  deadlineMin: number;
}) {
  const [remaining, setRemaining] = useState<number | null>(null);

  useEffect(() => {
    if (!firstMatchAt) return;
    const deadlineMs =
      new Date(firstMatchAt).getTime() - deadlineMin * 60_000;
    const deadlineIso = new Date(deadlineMs).toISOString();
    const update = () => setRemaining(minutesUntil(deadlineIso));
    update();
    const id = setInterval(update, 30_000);
    return () => clearInterval(id);
  }, [firstMatchAt, deadlineMin]);

  if (remaining === null) return null;

  const isUrgent = remaining <= 30;
  const hours = Math.floor(remaining / 60);
  const mins = remaining % 60;
  const label =
    hours > 0
      ? `${hours}h ${mins}m`
      : `${mins} minuto${mins !== 1 ? "s" : ""}`;

  return (
    <div
      role="status"
      aria-live="polite"
      className={`flex items-center gap-2 rounded-lg border px-4 py-2.5 text-sm font-medium ${
        isUrgent
          ? "border-vpv-danger/40 bg-vpv-danger/10 text-vpv-danger"
          : "border-amber-500/30 bg-amber-500/10 text-amber-400"
      }`}
    >
      <span aria-hidden="true">{isUrgent ? "!" : "\u23F1"}</span>
      <span>
        Deadline: <strong>{label}</strong>
      </span>
    </div>
  );
}

function MatchCards({
  matches,
  squad,
  selectedIds,
}: {
  matches: MatchEntry[];
  squad: SquadPlayerEntry[];
  selectedIds: Set<number>;
}) {
  const [open, setOpen] = useState(false);

  const squadByTeam = useMemo(() => {
    const map = new Map<string, SquadPlayerEntry[]>();
    for (const p of squad) {
      const list = map.get(p.team_name) ?? [];
      list.push(p);
      map.set(p.team_name, list);
    }
    return map;
  }, [squad]);

  if (matches.length === 0) return null;

  return (
    <div className="rounded-lg border border-vpv-border bg-vpv-card">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-3 py-2.5"
      >
        <span className="text-xs font-semibold uppercase tracking-wide text-vpv-text-muted">
          Partidos ({matches.length})
        </span>
        <svg
          width="14"
          height="14"
          viewBox="0 0 14 14"
          className={`text-vpv-text-muted transition-transform ${open ? "rotate-180" : ""}`}
        >
          <path
            d="M3.5 5.5l3.5 3.5 3.5-3.5"
            stroke="currentColor"
            strokeWidth="1.5"
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      {open && (
        <div className="divide-y divide-vpv-border/50 border-t border-vpv-border">
          {matches.map((m) => {
            const homePlayers = squadByTeam.get(m.home_team) ?? [];
            const awayPlayers = squadByTeam.get(m.away_team) ?? [];
            const hasPlayers =
              homePlayers.length > 0 || awayPlayers.length > 0;

            return (
              <div key={m.id} className="px-3 py-2">
                {/* Match header */}
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-vpv-text">
                    {m.home_team} - {m.away_team}
                  </span>
                  {m.played_at && (
                    <span className="text-xs text-vpv-text-muted">
                      {formatMatchTime(m.played_at)}
                    </span>
                  )}
                </div>

                {/* Squad players per team */}
                {hasPlayers && (
                  <div className="mt-1.5 grid grid-cols-2 gap-x-3">
                    <SquadColumn
                      players={homePlayers}
                      selectedIds={selectedIds}
                    />
                    <SquadColumn
                      players={awayPlayers}
                      selectedIds={selectedIds}
                    />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function SquadColumn({
  players,
  selectedIds,
}: {
  players: SquadPlayerEntry[];
  selectedIds: Set<number>;
}) {
  if (players.length === 0) return <div />;

  return (
    <div className="space-y-0.5">
      {players.map((p) => {
        const selected = selectedIds.has(p.player_id);
        const pos = p.position as Position;
        return (
          <div key={p.player_id} className="flex items-center gap-1.5">
            <span
              className={`rounded px-1 py-px text-[9px] font-bold ${POSITION_COLORS[pos]}`}
            >
              {pos}
            </span>
            <span
              className={`truncate text-xs ${
                selected
                  ? "font-semibold text-vpv-accent"
                  : "text-vpv-text-muted"
              }`}
            >
              {p.display_name}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function PlayerCard({
  player,
  isSelected,
  isDisabled,
  onToggle,
}: {
  player: SquadPlayerEntry;
  isSelected: boolean;
  isDisabled: boolean;
  onToggle: (player: SquadPlayerEntry) => void;
}) {
  const pos = player.position as Position;

  return (
    <button
      type="button"
      onClick={() => !isDisabled && onToggle(player)}
      disabled={isDisabled}
      className={`flex w-full items-center gap-2.5 rounded-lg border p-2.5 text-left transition-all ${
        isSelected
          ? "border-vpv-accent bg-vpv-accent/10"
          : isDisabled
            ? "cursor-not-allowed border-vpv-border bg-vpv-card opacity-40"
            : "border-vpv-card-border bg-vpv-card hover:border-vpv-border active:bg-vpv-bg"
      }`}
    >
      <PlayerAvatar
        photoPath={player.photo_path}
        name={player.display_name}
        size={36}
      />

      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-vpv-text">
          {player.display_name}
        </p>
        <p className="truncate text-xs text-vpv-text-muted">
          {player.team_name}
        </p>
      </div>

      <div className="flex shrink-0 flex-col items-end gap-0.5">
        <span
          className={`rounded border px-1.5 py-0.5 text-[10px] font-bold ${POSITION_COLORS[pos]}`}
        >
          {pos}
        </span>
        <span className="text-xs tabular-nums text-vpv-text-muted">
          {player.season_points} pts
        </span>
      </div>

      {isSelected && (
        <span aria-hidden="true" className="shrink-0 text-vpv-accent">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <circle cx="8" cy="8" r="8" fill="currentColor" opacity="0.2" />
            <path
              d="M4.5 8l2.5 2.5 4.5-5"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </span>
      )}
    </button>
  );
}

function PositionTabs({
  activeTab,
  onTabChange,
  counts,
  canAdd,
}: {
  activeTab: Position;
  onTabChange: (pos: Position) => void;
  counts: Record<Position, number>;
  canAdd: Record<Position, boolean>;
}) {
  return (
    <div
      className="flex rounded-xl bg-vpv-bg p-1"
      role="tablist"
      aria-label="Posiciones"
    >
      {POSITION_ORDER.map((pos) => {
        const active = pos === activeTab;
        const full = !canAdd[pos] && counts[pos] > 0;
        return (
          <button
            key={pos}
            role="tab"
            aria-selected={active}
            onClick={() => onTabChange(pos)}
            className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg py-2.5 text-sm font-medium transition-all ${
              active
                ? "bg-vpv-card text-vpv-text shadow-sm"
                : "text-vpv-text-muted hover:text-vpv-text"
            }`}
          >
            <span>{pos}</span>
            {counts[pos] > 0 && (
              <span
                className={`min-w-[18px] rounded-full px-1 text-center text-[11px] font-bold ${
                  full
                    ? "bg-vpv-success/20 text-vpv-success"
                    : "bg-vpv-accent/20 text-vpv-accent"
                }`}
              >
                {counts[pos]}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function AlineacionPage() {
  const params = useParams<{ numero: string }>();
  const numero = Number(params.numero);
  const { user, loading: authLoading } = useAuth();
  const { selectedSeason, loading: seasonLoading } = useSeason();

  // API calls
  const { data: myLineup, loading: myLineupLoading } =
    useFetch<MyLineupResponse>(
      selectedSeason ? `/lineups/${selectedSeason.id}/${numero}/me` : null,
    );

  const { data: matchdayData, loading: matchdayLoading } =
    useFetch<MatchdayDetailResponse>(
      selectedSeason ? `/matchdays/${selectedSeason.id}/${numero}` : null,
    );

  const { data: formationsData, loading: formationsLoading } = useFetch<
    ValidFormation[]
  >("/seasons/formations");

  // ---------------------------------------------------------------------------
  // Local state
  // ---------------------------------------------------------------------------

  const [selectedPlayers, setSelectedPlayers] = useState<SquadPlayerEntry[]>(
    [],
  );
  const [activeTab, setActiveTab] = useState<Position>("POR");
  const [submitting, setSubmitting] = useState(false);
  const [submitResult, setSubmitResult] = useState<{
    ok: boolean;
    message: string;
  } | null>(null);
  const [initialized, setInitialized] = useState(false);
  const prevCountRef = useRef(0);

  // Initialize from existing lineup
  useEffect(() => {
    if (initialized || !myLineup) return;

    if (myLineup.current_lineup) {
      const squadMap = new Map(myLineup.squad.map((s) => [s.player_id, s]));
      const preSelected: SquadPlayerEntry[] = [];
      for (const lp of myLineup.current_lineup.players) {
        const sq = squadMap.get(lp.player_id);
        if (sq) preSelected.push(sq);
      }
      setSelectedPlayers(preSelected);
    }

    setInitialized(true);
  }, [myLineup, initialized]);

  // ---------------------------------------------------------------------------
  // Derived values
  // ---------------------------------------------------------------------------

  const selectedIds = useMemo(
    () => new Set(selectedPlayers.map((p) => p.player_id)),
    [selectedPlayers],
  );

  const currentCounts = useMemo(
    () => countsByPosition(selectedPlayers),
    [selectedPlayers],
  );

  /** Formations still reachable with current selection. */
  const possibleFormations = useMemo(() => {
    if (!formationsData) return [];
    const c = currentCounts;
    return formationsData.filter(
      (f) =>
        c.DEF <= f.defenders &&
        c.MED <= f.midfielders &&
        c.DEL <= f.forwards,
    );
  }, [currentCounts, formationsData]);

  /** Exact formation when 11 players are selected. */
  const detectedFormation = useMemo<ValidFormation | null>(() => {
    if (selectedPlayers.length !== 11 || currentCounts.POR !== 1) return null;
    return (
      formationsData?.find(
        (f) =>
          f.defenders === currentCounts.DEF &&
          f.midfielders === currentCounts.MED &&
          f.forwards === currentCounts.DEL,
      ) ?? null
    );
  }, [selectedPlayers.length, currentCounts, formationsData]);

  /** Formation string for PitchView display. */
  const displayFormation =
    detectedFormation?.formation ??
    possibleFormations[0]?.formation ??
    "1-4-3-3";

  /** Whether each position can accept more players. */
  const canAdd = useMemo<Record<Position, boolean>>(
    () => ({
      POR: canAddToPosition(
        "POR",
        currentCounts,
        formationsData ?? [],
        selectedPlayers.length,
      ),
      DEF: canAddToPosition(
        "DEF",
        currentCounts,
        formationsData ?? [],
        selectedPlayers.length,
      ),
      MED: canAddToPosition(
        "MED",
        currentCounts,
        formationsData ?? [],
        selectedPlayers.length,
      ),
      DEL: canAddToPosition(
        "DEL",
        currentCounts,
        formationsData ?? [],
        selectedPlayers.length,
      ),
    }),
    [currentCounts, formationsData, selectedPlayers.length],
  );

  const lineupComplete = detectedFormation !== null;

  // Group squad players by position
  const playersByPosition = useMemo<Record<Position, SquadPlayerEntry[]>>(
    () => {
      const squad = myLineup?.squad ?? [];
      return {
        POR: squad
          .filter((p) => p.position === "POR")
          .sort((a, b) => b.season_points - a.season_points),
        DEF: squad
          .filter((p) => p.position === "DEF")
          .sort((a, b) => b.season_points - a.season_points),
        MED: squad
          .filter((p) => p.position === "MED")
          .sort((a, b) => b.season_points - a.season_points),
        DEL: squad
          .filter((p) => p.position === "DEL")
          .sort((a, b) => b.season_points - a.season_points),
      };
    },
    [myLineup],
  );

  // Build PitchView players
  const pitchPlayers = useMemo<PitchPlayer[]>(
    () =>
      selectedPlayers.map((p) => ({
        player_id: p.player_id,
        name: p.display_name,
        photo_path: p.photo_path,
        position_slot: p.position,
      })),
    [selectedPlayers],
  );

  // ---------------------------------------------------------------------------
  // Auto-advance tab when a position fills up (only on player addition)
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!formationsData || selectedPlayers.length <= prevCountRef.current) {
      prevCountRef.current = selectedPlayers.length;
      return;
    }
    prevCountRef.current = selectedPlayers.length;

    const counts = countsByPosition(selectedPlayers);
    if (
      !canAddToPosition(activeTab, counts, formationsData, selectedPlayers.length)
    ) {
      const nextTab = POSITION_ORDER.find((pos) =>
        canAddToPosition(pos, counts, formationsData, selectedPlayers.length),
      );
      if (nextTab) setActiveTab(nextTab);
    }
  }, [selectedPlayers, activeTab, formationsData]);

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  const handleTogglePlayer = useCallback(
    (player: SquadPlayerEntry) => {
      setSubmitResult(null);
      setSelectedPlayers((prev) => {
        const pos = player.position as Position;
        const isAlreadySelected = prev.some(
          (p) => p.player_id === player.player_id,
        );

        if (isAlreadySelected) {
          return prev.filter((p) => p.player_id !== player.player_id);
        }

        const counts = countsByPosition(prev);
        if (!canAddToPosition(pos, counts, formationsData ?? [], prev.length)) {
          return prev;
        }

        return [...prev, player];
      });
    },
    [formationsData],
  );

  const handleRemoveFromPitch = useCallback((playerId: number) => {
    setSubmitResult(null);
    setSelectedPlayers((prev) =>
      prev.filter((p) => p.player_id !== playerId),
    );
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!selectedSeason || !detectedFormation || submitting) return;

    setSubmitting(true);
    setSubmitResult(null);

    const body: LineupSubmitBody = {
      formation: detectedFormation.formation,
      players: selectedPlayers.map((p) => ({
        player_id: p.player_id,
        position_slot: p.position,
      })),
    };

    try {
      await apiClient.post(`/lineups/${selectedSeason.id}/${numero}`, body);
      setSubmitResult({
        ok: true,
        message: "Alineacion enviada. Revisa Telegram para la confirmacion.",
      });
    } catch (err) {
      const message =
        err instanceof ApiClientError
          ? err.error.message
          : "Error al enviar la alineacion.";
      setSubmitResult({ ok: false, message });
    } finally {
      setSubmitting(false);
    }
  }, [
    selectedSeason,
    detectedFormation,
    submitting,
    selectedPlayers,
    numero,
  ]);

  // ---------------------------------------------------------------------------
  // Loading / Error states
  // ---------------------------------------------------------------------------

  const isLoading =
    authLoading ||
    seasonLoading ||
    myLineupLoading ||
    matchdayLoading ||
    formationsLoading;

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="h-4 w-48 animate-pulse rounded bg-vpv-border" />
        <div className="h-8 w-64 animate-pulse rounded bg-vpv-border" />
        <div className="mx-auto aspect-[3/4] w-full max-w-sm animate-pulse rounded-xl bg-vpv-border" />
        <SkeletonTable rows={4} />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="py-12 text-center">
        <p className="text-vpv-text-muted">
          Debes{" "}
          <Link href="/login" className="text-vpv-accent underline">
            iniciar sesion
          </Link>{" "}
          para enviar tu alineacion.
        </p>
      </div>
    );
  }

  if (!selectedSeason) {
    return (
      <div className="py-12 text-center text-vpv-text-muted">
        No hay temporada activa.
      </div>
    );
  }

  if (!myLineup || !formationsData) {
    return (
      <div className="py-12 text-center text-vpv-text-muted">
        No se pudo cargar la informacion. Intentalo de nuevo.
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="space-y-5">
      {/* Breadcrumb */}
      <nav
        aria-label="Navegacion"
        className="flex items-center gap-2 text-sm text-vpv-text-muted"
      >
        <Link
          href="/jornadas"
          className="transition-colors hover:text-vpv-text"
        >
          Jornadas
        </Link>
        <span aria-hidden="true">/</span>
        <Link
          href={`/jornadas/${numero}`}
          className="transition-colors hover:text-vpv-text"
        >
          Jornada {numero}
        </Link>
        <span aria-hidden="true">/</span>
        <span className="text-vpv-text">Mi alineacion</span>
      </nav>

      {/* Header row */}
      <div className="flex items-baseline justify-between">
        <h1 className="text-xl font-bold text-vpv-text sm:text-2xl">
          Alineacion — J{numero}
        </h1>
        <span className="text-sm font-medium text-vpv-text-muted">
          {myLineup.display_name}
        </span>
      </div>

      {/* Deadline */}
      <DeadlineBanner
        firstMatchAt={matchdayData?.first_match_at ?? null}
        deadlineMin={myLineup.lineup_deadline_min}
      />

      {/* Formation auto-detect + counter */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {detectedFormation ? (
            <span className="rounded-lg border border-vpv-success/30 bg-vpv-success/10 px-3 py-1 text-sm font-bold text-vpv-success">
              {detectedFormation.formation}
            </span>
          ) : possibleFormations.length === 1 ? (
            <span className="rounded-lg border border-vpv-accent/30 bg-vpv-accent/10 px-3 py-1 text-sm font-bold text-vpv-accent">
              {possibleFormations[0].formation}
            </span>
          ) : possibleFormations.length > 1 && selectedPlayers.length > 0 ? (
            <span className="text-xs text-vpv-text-muted">
              {possibleFormations.length} formaciones posibles
            </span>
          ) : selectedPlayers.length > 0 && possibleFormations.length === 0 ? (
            <span className="text-xs text-vpv-danger">
              Combinacion no valida
            </span>
          ) : (
            <span className="text-sm text-vpv-text-muted">
              Selecciona 11 jugadores
            </span>
          )}
        </div>
        <span
          className={`text-sm font-bold tabular-nums ${
            lineupComplete ? "text-vpv-success" : "text-vpv-text"
          }`}
        >
          {selectedPlayers.length}/11
        </span>
      </div>

      {/* Two-column layout */}
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start">
        {/* PitchView + Matches: desktop left, mobile below selection */}
        <div className="order-2 w-full space-y-4 lg:order-1 lg:w-[380px] lg:shrink-0">
          <PitchView
            formation={displayFormation}
            players={pitchPlayers}
            onRemovePlayer={handleRemoveFromPitch}
          />

          {matchdayData && (
            <MatchCards
              matches={matchdayData.matches}
              squad={myLineup.squad}
              selectedIds={selectedIds}
            />
          )}
        </div>

        {/* Player selection: desktop right, mobile first */}
        <div className="order-1 flex-1 space-y-3 lg:order-2">
          <PositionTabs
            activeTab={activeTab}
            onTabChange={setActiveTab}
            counts={currentCounts}
            canAdd={canAdd}
          />

          {/* Active tab label */}
          <h2 className="text-xs font-semibold uppercase tracking-wide text-vpv-text-muted">
            {POSITION_LABELS[activeTab]}
          </h2>

          {/* Player grid for active tab */}
          <div className="grid gap-1.5 sm:grid-cols-2" role="tabpanel">
            {playersByPosition[activeTab].map((player) => {
              const isSelected = selectedIds.has(player.player_id);
              const isDisabled = !isSelected && !canAdd[activeTab];

              return (
                <PlayerCard
                  key={player.player_id}
                  player={player}
                  isSelected={isSelected}
                  isDisabled={isDisabled}
                  onToggle={handleTogglePlayer}
                />
              );
            })}
          </div>
        </div>
      </div>

      {/* Submit area */}
      <div className="sticky bottom-0 -mx-4 border-t border-vpv-border bg-vpv-bg px-4 py-4 sm:mx-0 sm:static sm:border-0 sm:bg-transparent sm:p-0">
        {submitResult && (
          <div
            role="alert"
            aria-live="assertive"
            className={`mb-3 rounded-lg border px-4 py-3 text-sm ${
              submitResult.ok
                ? "border-vpv-success/40 bg-vpv-success/10 text-vpv-success"
                : "border-vpv-danger/40 bg-vpv-danger/10 text-vpv-danger"
            }`}
          >
            {submitResult.message}
          </div>
        )}

        <button
          type="button"
          onClick={handleSubmit}
          disabled={!lineupComplete || submitting}
          className={`w-full rounded-lg px-6 py-3 text-sm font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-vpv-accent ${
            lineupComplete && !submitting
              ? "bg-vpv-accent text-white hover:bg-vpv-accent-hover"
              : "cursor-not-allowed bg-vpv-border text-vpv-text-muted"
          }`}
        >
          {submitting ? "Enviando..." : "Enviar alineacion"}
        </button>

        {!lineupComplete && selectedPlayers.length > 0 && (
          <p className="mt-2 text-center text-xs text-vpv-text-muted">
            Selecciona exactamente 11 jugadores
          </p>
        )}
      </div>
    </div>
  );
}
