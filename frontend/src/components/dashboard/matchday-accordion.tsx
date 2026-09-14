"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import type {
  MatchdayDetailResponse,
  LineupDetailResponse,
  LineupPlayerEntry,
  BenchPlayerEntry,
} from "@/types";
import { useFetch } from "@/hooks/use-fetch";
import { isMatchdayFinal } from "@/lib/matchday-status";
import { withSeason } from "@/lib/season-link";
import { formatEuros, weeklyAmounts } from "@/lib/weekly-payments";
import { PlayerAvatar } from "@/components/ui/player-avatar";
import styles from "./home.module.css";

const POSITION_COLORS: Record<string, string> = {
  POR: "bg-amber-500/20 text-amber-600 dark:text-amber-400",
  DEF: "bg-blue-500/20 text-blue-600 dark:text-blue-400",
  MED: "bg-green-500/20 text-green-600 dark:text-green-400",
  DEL: "bg-red-500/20 text-red-600 dark:text-red-400",
};

function PositionBadge({ pos }: { pos: string }) {
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${POSITION_COLORS[pos] ?? "bg-vpv-border text-vpv-text-muted"}`}
    >
      {pos}
    </span>
  );
}

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      className={`h-4 w-4 text-vpv-text-muted transition-transform duration-200 ${open ? "rotate-180" : ""}`}
      viewBox="0 0 20 20"
      fill="currentColor"
    >
      <path
        fillRule="evenodd"
        d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
        clipRule="evenodd"
      />
    </svg>
  );
}

type Breakdown = NonNullable<LineupPlayerEntry["score_breakdown"]>;

const STAT_LABELS: { key: string; label: string; get: (b: Breakdown) => number }[] = [
  { key: "play", label: "Juega", get: (b) => b.pts_play },
  { key: "starter", label: "Titular", get: (b) => b.pts_starter },
  { key: "result", label: "Resultado", get: (b) => b.pts_result },
  { key: "clean_sheet", label: "Imbatido", get: (b) => b.pts_clean_sheet },
  { key: "goals", label: "Goles", get: (b) => b.pts_goals },
  { key: "penalty_goals", label: "Gol penalti", get: (b) => b.pts_penalty_goals },
  { key: "assists", label: "Asistencias", get: (b) => b.pts_assists },
  { key: "penalties_saved", label: "Penalti parado", get: (b) => b.pts_penalties_saved },
  { key: "woodwork", label: "Tiro al palo", get: (b) => b.pts_woodwork },
  { key: "penalties_won", label: "Penalti forzado", get: (b) => b.pts_penalties_won },
  { key: "penalties_missed", label: "Penalti fallado", get: (b) => b.pts_penalties_missed },
  { key: "own_goals", label: "Gol propia", get: (b) => b.pts_own_goals },
  { key: "yellow", label: "Amarilla", get: (b) => b.pts_yellow },
  { key: "red", label: "Roja", get: (b) => b.pts_red },
  { key: "pen_committed", label: "Penalti cometido", get: (b) => b.pts_pen_committed },
  { key: "marca", label: "Marca", get: (b) => b.pts_marca },
  { key: "as", label: "As", get: (b) => b.pts_as },
];

function BreakdownGrid({ b }: { b: Breakdown }) {
  return (
    <div className="ml-8 mb-1.5 grid grid-cols-2 gap-x-4 gap-y-0.5 text-xs sm:grid-cols-3">
      {STAT_LABELS.map(({ key, label, get }) => {
        const val = get(b);
        if (val === 0) return null;
        return (
          <div key={key} className="flex items-center justify-between gap-2">
            <span className="text-vpv-text-muted">{label}</span>
            <span
              className={`font-bold tabular-nums ${val > 0 ? "text-vpv-success" : "text-vpv-danger"}`}
            >
              {val > 0 ? `+${val}` : val}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/**
 * One player of a lineup or bench. No breakdown means the stats are not in yet,
 * which is not the same as not having played: only a breakdown without the
 * points for playing says the player did not play.
 */
function PlayerLine({
  name,
  position,
  team,
  photo,
  points,
  b,
  bench = false,
  compact = false,
}: {
  name: string;
  position: string;
  team: string;
  photo: string | null;
  points: number;
  b: Breakdown | null | undefined;
  bench?: boolean;
  /** One line per player: a pending one shows ◷ instead of a note below it. */
  compact?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const hasBreakdown = b !== null && b !== undefined;
  const didNotPlay = hasBreakdown && b.pts_play <= 0;
  const dim = didNotPlay ? "opacity-45" : bench || !hasBreakdown ? "opacity-70" : "";

  return (
    <div>
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        aria-expanded={expanded}
        disabled={!hasBreakdown}
        className={`flex w-full items-center gap-2 py-1.5 text-sm text-left transition-colors hover:bg-vpv-bg/60 rounded px-1 -mx-1 ${dim}`}
      >
        <PlayerAvatar photoPath={photo} name={name} size={48} />
        <PositionBadge pos={position} />
        <span
          className={`min-w-0 flex-1 truncate ${didNotPlay ? "text-vpv-danger" : "text-vpv-text"}`}
        >
          {name}
          {didNotPlay && <span className="sr-only"> · no jugó</span>}
        </span>
        <span className="text-xs text-vpv-text-muted">{team}</span>
        <span className="w-8 text-right font-bold tabular-nums text-vpv-text">
          {hasBreakdown ? (
            points
          ) : compact ? (
            <>
              <span aria-hidden="true">◷</span>
              <span className="sr-only">pendiente de puntuar</span>
            </>
          ) : (
            "—"
          )}
        </span>
        {hasBreakdown ? <ChevronIcon open={expanded} /> : <span className="w-4" />}
      </button>

      {!hasBreakdown && !compact && (
        <p className="ml-8 text-xs text-vpv-text-muted">Sin desglose disponible</p>
      )}
      {expanded && hasBreakdown && <BreakdownGrid b={b} />}
    </div>
  );
}

function PlayerRow({ player, compact }: { player: LineupPlayerEntry; compact?: boolean }) {
  return (
    <PlayerLine
      name={player.player_name}
      position={player.position_slot}
      team={player.team_name}
      photo={player.photo_path}
      points={player.points}
      b={player.score_breakdown}
      compact={compact}
    />
  );
}

function BenchPlayerRow({ player, compact }: { player: BenchPlayerEntry; compact?: boolean }) {
  return (
    <PlayerLine
      name={player.player_name}
      position={player.position}
      team={player.team_name}
      photo={player.photo_path}
      points={player.matchday_points}
      b={player.score_breakdown}
      bench
      compact={compact}
    />
  );
}

/**
 * A lineup: the eleven with their points, the total and the bench. Shared by
 * the comparison and your own eleven, so both read a player the same way.
 * Compact folds the bench and marks a player still to be scored with ◷.
 */
export function LineupPlayers({
  lineup,
  compact = false,
}: {
  lineup: LineupDetailResponse;
  compact?: boolean;
}) {
  const bench = (
    <div className="divide-y divide-vpv-border/30">
      {lineup.bench.map((p) => (
        <BenchPlayerRow key={p.player_id} player={p} compact={compact} />
      ))}
    </div>
  );
  const benchTitle = `Banquillo (${lineup.bench.length})`;

  return (
    <div>
      <div className="divide-y divide-vpv-border/50">
        {lineup.players.map((p) => (
          <PlayerRow key={p.player_id} player={p} compact={compact} />
        ))}
        {!compact && (
          <div className="flex items-center justify-between pt-2 text-sm font-bold text-vpv-text">
            <span>Total</span>
            <span className="tabular-nums">{lineup.total_points}</span>
          </div>
        )}
      </div>

      {lineup.bench.length > 0 &&
        (compact ? (
          <details className="mt-2 border-t border-vpv-border pt-2">
            <summary className="min-h-8 cursor-pointer text-[11px] font-semibold uppercase tracking-wider text-vpv-text-muted">
              {benchTitle}
            </summary>
            {bench}
          </details>
        ) : (
          <div className="mt-3 border-t border-vpv-border pt-2">
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-vpv-text-muted">
              {benchTitle}
            </p>
            {bench}
          </div>
        ))}
    </div>
  );
}

function AccordionRow({
  score,
  rank,
  seasonId,
  matchdayNumber,
  personalPoints,
  isYou,
  refreshKey,
  amount,
}: {
  score: MatchdayDetailResponse["scores"][number];
  rank: number;
  seasonId: number;
  matchdayNumber: number;
  personalPoints?: number;
  isYou: boolean;
  refreshKey: number;
  /** What this place pays for the matchday; absent without weekly payments. */
  amount?: number;
}) {
  const [open, setOpen] = useState(false);
  const {
    data: lineup,
    loading,
    error,
    errorStatus,
    refetch,
  } = useFetch<LineupDetailResponse>(
    open ? `/matchdays/${seasonId}/${matchdayNumber}/lineup/${score.participant_id}` : null,
  );
  // The server refuses a rival's lineup until the deadline. That is the rule,
  // not a failure: say when it will show instead of offering a retry.
  const hidden = errorStatus === 403;
  const previousRefresh = useRef(refreshKey);
  useEffect(() => {
    if (previousRefresh.current !== refreshKey && open) refetch();
    previousRefresh.current = refreshKey;
  }, [refreshKey, open, refetch]);
  // Closing drops the request path and reopening restores it, so every reopen
  // asks again: a lineup refused before the deadline shows once it is public.
  function handleToggle() {
    setOpen((value) => !value);
  }

  return (
    <div className={styles.scoreRow} data-you={isYou}>
      <button
        type="button"
        onClick={handleToggle}
        aria-expanded={open}
        className={styles.scoreToggle}
      >
        <span className={styles.scoreRank}>{rank}</span>
        <span className="min-w-0 flex-1">
          <span className={styles.scoreName}>
            {score.display_name}
            {isYou && <span className={styles.you}>Tú</span>}
          </span>
          <span className="flex flex-wrap gap-x-2 text-xs text-vpv-text-muted">
            {score.formation && (
              <span className="mt-1 hidden text-[10px] sm:inline">{score.formation}</span>
            )}
            {score.pending_players > 0 && (
              <span className={styles.pending}>{score.pending_players} pendientes de puntuar</span>
            )}
          </span>
        </span>
        <span className={styles.scoreValue}>{score.total_points}</span>
        {personalPoints !== undefined && (
          <span className={styles.difference} title="Diferencia respecto a ti">
            {isYou
              ? "—"
              : `${score.total_points - personalPoints > 0 ? "+" : ""}${score.total_points - personalPoints}`}
          </span>
        )}
        {amount !== undefined && (
          <span className={styles.amount} data-pays={amount > 0} title="Pago semanal por este puesto">
            {amount > 0 ? formatEuros(amount) : "—"}
          </span>
        )}
        <ChevronIcon open={open} />
      </button>

      {open && (
        <div className="px-4 pb-3">
          {loading && (
            <div className="space-y-2 py-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="h-7 animate-pulse rounded bg-vpv-border" />
              ))}
            </div>
          )}

          {hidden && (
            <p className="py-2 text-xs text-vpv-text-muted">
              Su alineación se verá cuando cierre el plazo.
            </p>
          )}

          {lineup && <LineupPlayers lineup={lineup} />}

          {!loading && !hidden && (error || !lineup) && (
            <p className="py-2 text-xs text-vpv-text-muted">
              No se pudo cargar la plantilla.{" "}
              <button type="button" onClick={refetch} className="min-h-11 text-vpv-accent">
                Reintentar
              </button>
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export function MatchdayAccordion({
  data,
  seasonId,
  showHeader = true,
  participantId = null,
  refreshKey = 0,
  weeklyRules,
}: {
  data: MatchdayDetailResponse;
  seasonId: number;
  showHeader?: boolean;
  participantId?: number | null;
  refreshKey?: number;
  /** Position → euros; with it, each row shows what its place pays. */
  weeklyRules?: Record<number, number>;
}) {
  const yourPoints = data.scores.find(
    (entry) => entry.participant_id === participantId,
  )?.total_points;
  // What each place pays: only in a matchday that counts, and once there is a
  // ranking — before any stats everyone is tied, and a tie would charge them
  // all the worst place.
  const amounts =
    weeklyRules &&
    Object.keys(weeklyRules).length > 0 &&
    data.counts &&
    data.scores.some((s) => s.rank !== null)
      ? new Map(weeklyAmounts(data.scores, weeklyRules).map((e) => [e.participant_id, e.amount]))
      : null;

  return (
    <div className={styles.card}>
      {showHeader && (
        <div className={styles.cardHead}>
          <div>
            <p className={styles.cardKicker}>Así va tu liga</p>
            <h2 className={styles.cardTitle}>Jornada {data.number}</h2>
          </div>
          <Link href={withSeason(`/jornadas/${data.number}`, seasonId)} className={styles.textLink}>
            Ver completa <span aria-hidden="true">→</span>
          </Link>
        </div>
      )}
      <div className={styles.scoreNote}>
        <span className={styles.status}>
          {isMatchdayFinal(data)
            ? "Resultados finales"
            : "Provisional · las estadísticas pueden cambiar"}
        </span>
      </div>
      <details className={styles.help}>
        <summary>Cómo leer la comparación</summary>
        <p>
          Pendientes de puntuar no significa necesariamente pendientes de jugar. Abre un
          participante para comparar su once y banquillo. La diferencia indica sus puntos respecto a
          los tuyos.
        </p>
      </details>
      <div className={styles.columns} aria-hidden="true">
        <span>Participante · abre su once</span>
        <span>
          Puntos{participantId !== null ? " / vs. tú" : ""}
          {amounts ? " / €" : ""}
        </span>
      </div>
      {data.scores.length === 0 && (
        <p className="p-4 text-sm text-vpv-text-muted">Todavía no hay puntuaciones disponibles.</p>
      )}
      <div>
        {data.scores.map((s, i) => (
          <AccordionRow
            key={`${seasonId}:${data.number}:${s.participant_id}`}
            refreshKey={refreshKey}
            score={s}
            rank={s.rank ?? i + 1}
            isYou={s.participant_id === participantId}
            personalPoints={yourPoints}
            seasonId={seasonId}
            matchdayNumber={data.number}
            amount={amounts?.get(s.participant_id)}
          />
        ))}
      </div>
    </div>
  );
}
