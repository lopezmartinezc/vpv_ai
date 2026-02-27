"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import { apiClient, ApiClientError } from "@/lib/api-client";
import { PlayerAvatar } from "@/components/ui/player-avatar";
import { SkeletonTable } from "@/components/ui/skeleton";
import type {
  SquadListResponse,
  SquadDetailResponse,
  SquadPlayerEntry,
  ValidFormation,
} from "@/types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface LineupSubmitBody {
  formation: string;
  players: { player_id: number; position_slot: string }[];
}

interface LineupSubmitResponse {
  ok: boolean;
  message?: string;
}

/** Required slots for each position given a formation string like "1-4-3-3" */
interface FormationSlots {
  POR: number;
  DEF: number;
  MED: number;
  DEL: number;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

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

function parseFormationSlots(formation: string): FormationSlots {
  const parts = formation.split("-").map(Number);
  // parts[0] is always 1 (goalkeeper), parts[1] DEF, parts[2] MED, parts[3] DEL
  return {
    POR: 1,
    DEF: parts[1] ?? 0,
    MED: parts[2] ?? 0,
    DEL: parts[3] ?? 0,
  };
}

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

function isLineupComplete(
  selected: SquadPlayerEntry[],
  slots: FormationSlots,
): boolean {
  if (selected.length !== 11) return false;
  const counts = countsByPosition(selected);
  return (
    counts.POR === slots.POR &&
    counts.DEF === slots.DEF &&
    counts.MED === slots.MED &&
    counts.DEL === slots.DEL
  );
}

/** Build position_slot label: "DEF_1", "DEF_2", ... etc. for the submit body */
function buildPlayerSlots(
  selected: SquadPlayerEntry[],
): { player_id: number; position_slot: string }[] {
  const counters: Partial<Record<Position, number>> = {};
  return selected.map((p) => {
    const pos = p.position as Position;
    counters[pos] = (counters[pos] ?? 0) + 1;
    return {
      player_id: p.player_id,
      position_slot: `${pos}_${counters[pos]}`,
    };
  });
}

/** Minutes until a future date, or null if already passed */
function minutesUntil(isoDate: string | null): number | null {
  if (!isoDate) return null;
  const diff = new Date(isoDate).getTime() - Date.now();
  return diff > 0 ? Math.floor(diff / 60_000) : null;
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
    hours > 0 ? `${hours}h ${mins}m` : `${mins} minuto${mins !== 1 ? "s" : ""}`;

  return (
    <div
      role="status"
      aria-live="polite"
      className={`flex items-center gap-2 rounded-lg border px-4 py-3 text-sm font-medium ${
        isUrgent
          ? "border-vpv-danger/40 bg-vpv-danger/10 text-vpv-danger"
          : "border-amber-500/30 bg-amber-500/10 text-amber-400"
      }`}
    >
      <span aria-hidden="true">{isUrgent ? "!" : "⏱"}</span>
      <span>
        Deadline alineacion: <strong>{label}</strong> restantes
      </span>
    </div>
  );
}

function FormationSelector({
  formations,
  selected,
  onChange,
}: {
  formations: ValidFormation[];
  selected: string;
  onChange: (f: string) => void;
}) {
  return (
    <div className="space-y-2">
      <label
        htmlFor="formation-select"
        className="block text-sm font-semibold uppercase tracking-wide text-vpv-text-muted"
      >
        Formacion
      </label>
      <select
        id="formation-select"
        value={selected}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-vpv-border bg-vpv-card px-3 py-2 text-sm text-vpv-text focus:border-vpv-accent focus:outline-none focus:ring-1 focus:ring-vpv-accent sm:w-48"
      >
        {formations.map((f) => (
          <option key={f.id} value={f.formation}>
            {f.formation}
          </option>
        ))}
      </select>
    </div>
  );
}

function PositionCounter({
  position,
  current,
  required,
}: {
  position: Position;
  current: number;
  required: number;
}) {
  const isFull = current === required;
  const isOver = current > required;

  return (
    <div
      className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium ${
        isOver
          ? "border-vpv-danger/40 bg-vpv-danger/10 text-vpv-danger"
          : isFull
            ? "border-vpv-success/40 bg-vpv-success/10 text-vpv-success"
            : POSITION_COLORS[position]
      }`}
    >
      <span>{position}</span>
      <span className="font-bold tabular-nums">
        {current}/{required}
      </span>
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

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      if (!isDisabled) onToggle(player);
    }
  };

  return (
    <div
      role="checkbox"
      aria-checked={isSelected}
      aria-disabled={isDisabled}
      tabIndex={isDisabled ? -1 : 0}
      onClick={() => !isDisabled && onToggle(player)}
      onKeyDown={handleKeyDown}
      className={`flex cursor-pointer items-center gap-3 rounded-lg border p-3 transition-all select-none ${
        isSelected
          ? "border-vpv-accent bg-vpv-accent/10"
          : isDisabled
            ? "cursor-not-allowed border-vpv-border bg-vpv-card opacity-40"
            : "border-vpv-card-border bg-vpv-card hover:border-vpv-border hover:bg-vpv-bg"
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
        <p className="truncate text-xs text-vpv-text-muted">{player.team_name}</p>
      </div>

      <div className="flex shrink-0 flex-col items-end gap-1">
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
        <span
          aria-hidden="true"
          className="shrink-0 text-vpv-accent"
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            aria-hidden="true"
          >
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

  // Fetch all squads to resolve the user's participant_id
  const { data: squadList, loading: squadListLoading } =
    useFetch<SquadListResponse>(
      selectedSeason ? `/squads/${selectedSeason.id}` : null,
    );

  // Derive participant_id by matching display_name
  const participantId = useMemo(() => {
    if (!squadList || !user) return null;
    const match = squadList.squads.find(
      (s) => s.display_name.toLowerCase() === user.displayName.toLowerCase(),
    );
    return match?.participant_id ?? null;
  }, [squadList, user]);

  // Fetch the user's full squad (player list)
  const { data: squadDetail, loading: squadDetailLoading } =
    useFetch<SquadDetailResponse>(
      selectedSeason && participantId !== null
        ? `/squads/${selectedSeason.id}/${participantId}`
        : null,
    );

  // Fetch valid formations
  const { data: formationsData, loading: formationsLoading } = useFetch<
    ValidFormation[]
  >(selectedSeason ? `/seasons/${selectedSeason.id}/valid-formations` : null);

  // ---------------------------------------------------------------------------
  // Local state
  // ---------------------------------------------------------------------------

  const [selectedFormation, setSelectedFormation] = useState<string>("");
  const [selectedPlayers, setSelectedPlayers] = useState<SquadPlayerEntry[]>(
    [],
  );
  const [submitting, setSubmitting] = useState(false);
  const [submitResult, setSubmitResult] = useState<{
    ok: boolean;
    message: string;
  } | null>(null);

  // Set default formation once data arrives
  useEffect(() => {
    if (formationsData && formationsData.length > 0 && !selectedFormation) {
      setSelectedFormation(formationsData[0].formation);
    }
  }, [formationsData, selectedFormation]);

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

  const lineupComplete = useMemo(
    () => isLineupComplete(selectedPlayers, formationSlots),
    [selectedPlayers, formationSlots],
  );

  // Group squad players by position
  const playersByPosition = useMemo<Record<Position, SquadPlayerEntry[]>>(
    () => ({
      POR:
        squadDetail?.players
          .filter((p) => p.position === "POR")
          .sort((a, b) => b.season_points - a.season_points) ?? [],
      DEF:
        squadDetail?.players
          .filter((p) => p.position === "DEF")
          .sort((a, b) => b.season_points - a.season_points) ?? [],
      MED:
        squadDetail?.players
          .filter((p) => p.position === "MED")
          .sort((a, b) => b.season_points - a.season_points) ?? [],
      DEL:
        squadDetail?.players
          .filter((p) => p.position === "DEL")
          .sort((a, b) => b.season_points - a.season_points) ?? [],
    }),
    [squadDetail],
  );

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

        // Prevent adding more than required for this position
        const currentForPos = prev.filter((p) => p.position === pos).length;
        if (currentForPos >= formationSlots[pos]) return prev;

        // Prevent exceeding 11 total
        if (prev.length >= 11) return prev;

        return [...prev, player];
      });
    },
    [formationSlots],
  );

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
      players: buildPlayerSlots(selectedPlayers),
    };

    try {
      await apiClient.post<LineupSubmitResponse>(
        `/lineups/${selectedSeason.id}/${numero}`,
        body,
      );
      setSubmitResult({
        ok: true,
        message:
          "Alineacion enviada correctamente. Revisa Telegram para la confirmacion.",
      });
    } catch (err) {
      const message =
        err instanceof ApiClientError
          ? err.error.message
          : "Error al enviar la alineacion. Intentalo de nuevo.";
      setSubmitResult({ ok: false, message });
    } finally {
      setSubmitting(false);
    }
  }, [selectedSeason, lineupComplete, submitting, selectedFormation, selectedPlayers, numero]);

  // ---------------------------------------------------------------------------
  // Loading state
  // ---------------------------------------------------------------------------

  const isLoading =
    authLoading ||
    seasonLoading ||
    squadListLoading ||
    squadDetailLoading ||
    formationsLoading;

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="h-4 w-48 animate-pulse rounded bg-vpv-border" />
        <div className="h-8 w-64 animate-pulse rounded bg-vpv-border" />
        <div className="h-10 w-40 animate-pulse rounded bg-vpv-border" />
        <SkeletonTable rows={6} />
        <SkeletonTable rows={6} />
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Error / no-data states
  // ---------------------------------------------------------------------------

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

  if (participantId === null) {
    return (
      <div className="py-12 text-center text-vpv-text-muted">
        No se encontro tu plantilla para esta temporada.
      </div>
    );
  }

  if (!squadDetail || !formationsData) {
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
    <div className="space-y-6">
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

      {/* Page heading */}
      <div className="flex items-baseline justify-between">
        <h1 className="text-2xl font-bold text-vpv-text">
          Alineacion — Jornada {numero}
        </h1>
      </div>

      {/* Deadline banner */}
      <DeadlineBanner
        firstMatchAt={null}
        deadlineMin={30}
      />

      {/* Formation selector */}
      <FormationSelector
        formations={formationsData}
        selected={selectedFormation}
        onChange={handleFormationChange}
      />

      {/* Position counters */}
      <div
        aria-label="Jugadores seleccionados por posicion"
        className="flex flex-wrap gap-2"
      >
        {POSITION_ORDER.map((pos) => (
          <PositionCounter
            key={pos}
            position={pos}
            current={currentCounts[pos]}
            required={formationSlots[pos]}
          />
        ))}
        <span className="ml-auto text-sm font-medium text-vpv-text-muted">
          Total:{" "}
          <span
            className={`tabular-nums font-bold ${selectedPlayers.length === 11 ? "text-vpv-success" : "text-vpv-text"}`}
          >
            {selectedPlayers.length}/11
          </span>
        </span>
      </div>

      {/* Player picker grouped by position */}
      <div className="space-y-6">
        {POSITION_ORDER.map((pos) => {
          const players = playersByPosition[pos];
          if (players.length === 0) return null;

          const posRequired = formationSlots[pos];
          const posCurrent = currentCounts[pos];
          const posIsFull = posCurrent >= posRequired;

          return (
            <section key={pos} aria-labelledby={`pos-heading-${pos}`}>
              <div className="mb-3 flex items-center gap-2">
                <h2
                  id={`pos-heading-${pos}`}
                  className="text-sm font-semibold uppercase tracking-wide text-vpv-text-muted"
                >
                  {POSITION_LABELS[pos]}
                </h2>
                <span
                  className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${POSITION_COLORS[pos]}`}
                >
                  {posCurrent}/{posRequired}
                </span>
              </div>

              <div
                role="group"
                aria-label={`${POSITION_LABELS[pos]} disponibles`}
                className="grid gap-2 sm:grid-cols-2"
              >
                {players.map((player) => {
                  const isSelected = selectedIds.has(player.player_id);
                  // Disable if position is full and player is not selected
                  const isDisabled = !isSelected && posIsFull;

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
            </section>
          );
        })}
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
          aria-disabled={!lineupComplete || submitting}
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
            Selecciona exactamente 11 jugadores segun la formacion elegida
          </p>
        )}
      </div>
    </div>
  );
}
