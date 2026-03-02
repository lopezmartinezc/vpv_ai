"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
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

interface FormationSlots {
  POR: number;
  DEF: number;
  MED: number;
  DEL: number;
}

function parseFormationSlots(formation: string): FormationSlots {
  const parts = formation.split("-").map(Number);
  return { POR: 1, DEF: parts[1] ?? 0, MED: parts[2] ?? 0, DEL: parts[3] ?? 0 };
}

function countsByPosition(selected: SquadPlayerEntry[]): Record<Position, number> {
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
  const time = d.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
  return `${day} ${time}`;
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
    const deadlineMs = new Date(firstMatchAt).getTime() - deadlineMin * 60_000;
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
    hours > 0 ? `${hours}h ${mins}m` : `${mins} minuto${mins !== 1 ? "s" : ""}`;

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

function FormationChips({
  formations,
  selected,
  onChange,
}: {
  formations: ValidFormation[];
  selected: string;
  onChange: (f: string) => void;
}) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-1" role="radiogroup" aria-label="Formacion">
      {formations.map((f) => {
        const isActive = f.formation === selected;
        return (
          <button
            key={f.id}
            type="button"
            role="radio"
            aria-checked={isActive}
            onClick={() => onChange(f.formation)}
            className={`shrink-0 rounded-lg border px-3 py-1.5 text-sm font-semibold transition-colors ${
              isActive
                ? "border-vpv-accent bg-vpv-accent/15 text-vpv-accent"
                : "border-vpv-border bg-vpv-card text-vpv-text-muted hover:border-vpv-accent/40"
            }`}
          >
            {f.formation}
          </button>
        );
      })}
    </div>
  );
}

function MatchStrip({ matches }: { matches: MatchEntry[] }) {
  if (matches.length === 0) return null;

  return (
    <div className="space-y-1.5">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-vpv-text-muted">
        Partidos
      </h3>
      <div className="flex gap-2 overflow-x-auto pb-1">
        {matches.map((m) => (
          <div
            key={m.id}
            className="shrink-0 rounded-lg border border-vpv-border bg-vpv-card px-3 py-1.5 text-xs"
          >
            <span className="font-medium text-vpv-text">
              {m.home_team} - {m.away_team}
            </span>
            {m.played_at && (
              <span className="ml-1.5 text-vpv-text-muted">
                {formatMatchTime(m.played_at)}
              </span>
            )}
          </div>
        ))}
      </div>
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
      <PlayerAvatar photoPath={player.photo_path} name={player.display_name} size={36} />

      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-vpv-text">
          {player.display_name}
        </p>
        <p className="truncate text-xs text-vpv-text-muted">{player.team_name}</p>
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

function PositionSection({
  position,
  players,
  selectedIds,
  currentCount,
  requiredCount,
  onToggle,
}: {
  position: Position;
  players: SquadPlayerEntry[];
  selectedIds: Set<number>;
  currentCount: number;
  requiredCount: number;
  onToggle: (player: SquadPlayerEntry) => void;
}) {
  const isFull = currentCount >= requiredCount;
  const [collapsed, setCollapsed] = useState(false);

  // Auto-collapse when full
  useEffect(() => {
    if (isFull) setCollapsed(true);
    else setCollapsed(false);
  }, [isFull]);

  if (players.length === 0) return null;

  return (
    <section>
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        className="mb-2 flex w-full items-center gap-2"
      >
        <h2 className="text-sm font-semibold uppercase tracking-wide text-vpv-text-muted">
          {POSITION_LABELS[position]}
        </h2>
        <span
          className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${
            isFull
              ? "border-vpv-success/40 bg-vpv-success/10 text-vpv-success"
              : POSITION_COLORS[position]
          }`}
        >
          {currentCount}/{requiredCount}
        </span>
        <svg
          width="12"
          height="12"
          viewBox="0 0 12 12"
          className={`ml-auto text-vpv-text-muted transition-transform ${collapsed ? "" : "rotate-180"}`}
        >
          <path d="M3 5l3 3 3-3" stroke="currentColor" strokeWidth="1.5" fill="none" />
        </svg>
      </button>

      {!collapsed && (
        <div className="grid gap-1.5 sm:grid-cols-2">
          {players.map((player) => {
            const isSelected = selectedIds.has(player.player_id);
            const isDisabled = !isSelected && isFull;

            return (
              <PlayerCard
                key={player.player_id}
                player={player}
                isSelected={isSelected}
                isDisabled={isDisabled}
                onToggle={onToggle}
              />
            );
          })}
        </div>
      )}
    </section>
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
  const { data: myLineup, loading: myLineupLoading } = useFetch<MyLineupResponse>(
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

  const [selectedFormation, setSelectedFormation] = useState<string>("");
  const [selectedPlayers, setSelectedPlayers] = useState<SquadPlayerEntry[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [submitResult, setSubmitResult] = useState<{
    ok: boolean;
    message: string;
  } | null>(null);
  const [initialized, setInitialized] = useState(false);

  // Initialize from existing lineup + set default formation
  useEffect(() => {
    if (initialized || !myLineup || !formationsData) return;

    if (myLineup.current_lineup) {
      // Pre-load existing lineup
      setSelectedFormation(myLineup.current_lineup.formation);

      // Map lineup players back to squad entries
      const squadMap = new Map(myLineup.squad.map((s) => [s.player_id, s]));
      const preSelected: SquadPlayerEntry[] = [];
      for (const lp of myLineup.current_lineup.players) {
        const sq = squadMap.get(lp.player_id);
        if (sq) preSelected.push(sq);
      }
      setSelectedPlayers(preSelected);
    } else if (formationsData.length > 0) {
      setSelectedFormation(formationsData[0].formation);
    }

    setInitialized(true);
  }, [myLineup, formationsData, initialized]);

  // ---------------------------------------------------------------------------
  // Derived values
  // ---------------------------------------------------------------------------

  const formationSlots = useMemo(
    () => parseFormationSlots(selectedFormation || "1-4-3-3"),
    [selectedFormation],
  );

  const selectedIds = useMemo(
    () => new Set(selectedPlayers.map((p) => p.player_id)),
    [selectedPlayers],
  );

  const currentCounts = useMemo(
    () => countsByPosition(selectedPlayers),
    [selectedPlayers],
  );

  const lineupComplete = useMemo(() => {
    if (selectedPlayers.length !== 11) return false;
    const counts = countsByPosition(selectedPlayers);
    return (
      counts.POR === formationSlots.POR &&
      counts.DEF === formationSlots.DEF &&
      counts.MED === formationSlots.MED &&
      counts.DEL === formationSlots.DEL
    );
  }, [selectedPlayers, formationSlots]);

  // Group squad players by position
  const playersByPosition = useMemo<Record<Position, SquadPlayerEntry[]>>(() => {
    const squad = myLineup?.squad ?? [];
    return {
      POR: squad.filter((p) => p.position === "POR").sort((a, b) => b.season_points - a.season_points),
      DEF: squad.filter((p) => p.position === "DEF").sort((a, b) => b.season_points - a.season_points),
      MED: squad.filter((p) => p.position === "MED").sort((a, b) => b.season_points - a.season_points),
      DEL: squad.filter((p) => p.position === "DEL").sort((a, b) => b.season_points - a.season_points),
    };
  }, [myLineup]);

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
  // Handlers
  // ---------------------------------------------------------------------------

  const handleTogglePlayer = useCallback(
    (player: SquadPlayerEntry) => {
      setSubmitResult(null);
      setSelectedPlayers((prev) => {
        const pos = player.position as Position;
        const isAlreadySelected = prev.some((p) => p.player_id === player.player_id);

        if (isAlreadySelected) {
          return prev.filter((p) => p.player_id !== player.player_id);
        }

        const currentForPos = prev.filter((p) => p.position === pos).length;
        if (currentForPos >= formationSlots[pos]) return prev;
        if (prev.length >= 11) return prev;

        return [...prev, player];
      });
    },
    [formationSlots],
  );

  const handleRemoveFromPitch = useCallback((playerId: number) => {
    setSubmitResult(null);
    setSelectedPlayers((prev) => prev.filter((p) => p.player_id !== playerId));
  }, []);

  const handleFormationChange = useCallback((formation: string) => {
    setSelectedFormation(formation);
    setSelectedPlayers([]);
    setSubmitResult(null);
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!selectedSeason || !lineupComplete || submitting) return;

    setSubmitting(true);
    setSubmitResult(null);

    const body: LineupSubmitBody = {
      formation: selectedFormation,
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
  }, [selectedSeason, lineupComplete, submitting, selectedFormation, selectedPlayers, numero]);

  // ---------------------------------------------------------------------------
  // Loading / Error states
  // ---------------------------------------------------------------------------

  const isLoading =
    authLoading || seasonLoading || myLineupLoading || matchdayLoading || formationsLoading;

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
        <Link href="/jornadas" className="transition-colors hover:text-vpv-text">
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

      {/* Formation chips */}
      <FormationChips
        formations={formationsData}
        selected={selectedFormation}
        onChange={handleFormationChange}
      />

      {/* Two-column layout on desktop */}
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start">
        {/* Left: PitchView + Matches */}
        <div className="w-full space-y-4 lg:w-[380px] lg:shrink-0">
          <PitchView
            formation={selectedFormation}
            players={pitchPlayers}
            onRemovePlayer={handleRemoveFromPitch}
          />

          {/* Match strip */}
          {matchdayData && <MatchStrip matches={matchdayData.matches} />}
        </div>

        {/* Right: Player selection */}
        <div className="flex-1 space-y-4">
          {/* Position counters summary */}
          <div className="flex flex-wrap gap-2" aria-label="Resumen posiciones">
            {POSITION_ORDER.map((pos) => {
              const cur = currentCounts[pos];
              const req = formationSlots[pos];
              const isFull = cur === req;
              return (
                <span
                  key={pos}
                  className={`rounded-full border px-2.5 py-0.5 text-xs font-bold ${
                    isFull
                      ? "border-vpv-success/40 bg-vpv-success/10 text-vpv-success"
                      : POSITION_COLORS[pos]
                  }`}
                >
                  {pos} {cur}/{req}
                </span>
              );
            })}
            <span className="ml-auto text-sm font-medium text-vpv-text-muted">
              <span
                className={`tabular-nums font-bold ${selectedPlayers.length === 11 ? "text-vpv-success" : "text-vpv-text"}`}
              >
                {selectedPlayers.length}/11
              </span>
            </span>
          </div>

          {/* Player lists by position */}
          {POSITION_ORDER.map((pos) => (
            <PositionSection
              key={pos}
              position={pos}
              players={playersByPosition[pos]}
              selectedIds={selectedIds}
              currentCount={currentCounts[pos]}
              requiredCount={formationSlots[pos]}
              onToggle={handleTogglePlayer}
            />
          ))}
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
            Selecciona exactamente 11 jugadores segun la formacion
          </p>
        )}
      </div>
    </div>
  );
}
