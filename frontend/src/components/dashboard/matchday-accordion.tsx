"use client";

import { useState } from "react";
import Link from "next/link";
import type {
  MatchdayDetailResponse,
  LineupDetailResponse,
  LineupPlayerEntry,
  BenchPlayerEntry,
} from "@/types";
import { apiClient } from "@/lib/api-client";
import { PlayerAvatar } from "@/components/ui/player-avatar";

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

const STAT_LABELS = [
  { key: "play", label: "Juega", get: (b: NonNullable<LineupPlayerEntry["score_breakdown"]>) => b.pts_play },
  { key: "starter", label: "Titular", get: (b: NonNullable<LineupPlayerEntry["score_breakdown"]>) => b.pts_starter },
  { key: "result", label: "Resultado", get: (b: NonNullable<LineupPlayerEntry["score_breakdown"]>) => b.pts_result },
  { key: "clean_sheet", label: "Imbatido", get: (b: NonNullable<LineupPlayerEntry["score_breakdown"]>) => b.pts_clean_sheet },
  { key: "goals", label: "Goles", get: (b: NonNullable<LineupPlayerEntry["score_breakdown"]>) => b.pts_goals },
  { key: "assists", label: "Asistencias", get: (b: NonNullable<LineupPlayerEntry["score_breakdown"]>) => b.pts_assists },
  { key: "yellow", label: "Amarilla", get: (b: NonNullable<LineupPlayerEntry["score_breakdown"]>) => b.pts_yellow },
  { key: "red", label: "Roja", get: (b: NonNullable<LineupPlayerEntry["score_breakdown"]>) => b.pts_red },
  { key: "marca", label: "Marca", get: (b: NonNullable<LineupPlayerEntry["score_breakdown"]>) => b.pts_marca },
  { key: "as", label: "As", get: (b: NonNullable<LineupPlayerEntry["score_breakdown"]>) => b.pts_as },
];

function PlayerRow({ player }: { player: LineupPlayerEntry }) {
  const [expanded, setExpanded] = useState(false);
  const b = player.score_breakdown;
  const didPlay = b ? b.pts_play > 0 : false;

  return (
    <div>
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className={`flex w-full items-center gap-2 py-1.5 text-sm text-left transition-colors hover:bg-vpv-bg/60 rounded px-1 -mx-1 ${
          !didPlay ? "opacity-45" : ""
        }`}
      >
        <PlayerAvatar photoPath={player.photo_path} name={player.player_name} size={48} />
        <PositionBadge pos={player.position_slot} />
        <span className={`min-w-0 flex-1 truncate ${!didPlay ? "text-vpv-danger" : "text-vpv-text"}`}>
          {player.player_name}
        </span>
        <span className="text-xs text-vpv-text-muted">{player.team_name}</span>
        <span className="w-8 text-right font-bold tabular-nums text-vpv-text">
          {player.points}
        </span>
        {didPlay && b ? <ChevronIcon open={expanded} /> : <span className="w-4" />}
      </button>

      {expanded && didPlay && b && (
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
      )}
    </div>
  );
}

function BenchPlayerRow({ player }: { player: BenchPlayerEntry }) {
  const [expanded, setExpanded] = useState(false);
  const b = player.score_breakdown;
  const didPlay = b ? b.pts_play > 0 : false;

  return (
    <div>
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className={`flex w-full items-center gap-2 py-1.5 text-sm text-left transition-colors hover:bg-vpv-bg/60 rounded px-1 -mx-1 ${
          !didPlay ? "opacity-45" : "opacity-70"
        }`}
      >
        <PlayerAvatar photoPath={player.photo_path} name={player.player_name} size={48} />
        <PositionBadge pos={player.position} />
        <span className={`min-w-0 flex-1 truncate ${!didPlay ? "text-vpv-danger" : "text-vpv-text"}`}>
          {player.player_name}
        </span>
        <span className="text-xs text-vpv-text-muted">{player.team_name}</span>
        <span className="w-8 text-right font-bold tabular-nums text-vpv-text">
          {player.matchday_points}
        </span>
        {didPlay && b ? <ChevronIcon open={expanded} /> : <span className="w-4" />}
      </button>

      {expanded && didPlay && b && (
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
      )}
    </div>
  );
}

function AccordionRow({
  score,
  rank,
  seasonId,
  matchdayNumber,
}: {
  score: MatchdayDetailResponse["scores"][number];
  rank: number;
  seasonId: number;
  matchdayNumber: number;
}) {
  const [open, setOpen] = useState(false);
  const [lineup, setLineup] = useState<LineupDetailResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const isFirst = rank === 1;

  function handleToggle() {
    if (!open && !lineup && !loading) {
      setLoading(true);
      apiClient
        .get<LineupDetailResponse>(
          `/matchdays/${seasonId}/${matchdayNumber}/lineup/${score.participant_id}`,
        )
        .then((data) => setLineup(data))
        .catch(() => {})
        .finally(() => setLoading(false));
    }
    setOpen((prev) => !prev);
  }

  return (
    <div
      className={`border-b border-vpv-border last:border-0 ${open ? "bg-vpv-bg/50" : ""}`}
    >
      <button
        type="button"
        onClick={handleToggle}
        className="flex w-full items-center gap-2 px-4 py-3 text-left transition-colors hover:bg-vpv-bg/80 active:scale-[0.995]"
      >
        <span
          className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
            isFirst
              ? "bg-vpv-gold text-black"
              : "bg-vpv-border text-vpv-text-muted"
          }`}
        >
          {rank}
        </span>
        <span
          className={`min-w-0 flex-1 truncate font-medium ${
            isFirst ? "text-vpv-accent" : "text-vpv-text"
          }`}
        >
          {score.display_name}
        </span>
        {score.formation && (
          <span className="hidden text-xs text-vpv-text-muted sm:inline">
            {score.formation}
          </span>
        )}
        <span
          className={`min-w-[3rem] text-right text-lg font-bold tabular-nums ${
            isFirst ? "text-vpv-accent" : "text-vpv-text"
          }`}
        >
          {score.total_points}
        </span>
        <ChevronIcon open={open} />
      </button>

      {open && (
        <div className="px-4 pb-3">
          {loading && (
            <div className="space-y-2 py-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <div
                  key={i}
                  className="h-7 animate-pulse rounded bg-vpv-border"
                />
              ))}
            </div>
          )}

          {lineup && (
            <div>
              <div className="divide-y divide-vpv-border/50">
                {lineup.players.map((p) => (
                  <PlayerRow key={p.player_id} player={p} />
                ))}
                <div className="flex items-center justify-between pt-2 text-sm font-bold text-vpv-text">
                  <span>Total</span>
                  <span className="tabular-nums">{lineup.total_points}</span>
                </div>
              </div>

              {lineup.bench.length > 0 && (
                <div className="mt-3 border-t border-vpv-border pt-2">
                  <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-vpv-text-muted">
                    Banquillo ({lineup.bench.length})
                  </p>
                  <div className="divide-y divide-vpv-border/30">
                    {lineup.bench.map((p) => (
                      <BenchPlayerRow key={p.player_id} player={p} />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {!loading && !lineup && (
            <p className="py-2 text-xs text-vpv-text-muted">
              No se pudo cargar la plantilla
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
}: {
  data: MatchdayDetailResponse;
  seasonId: number;
  showHeader?: boolean;
}) {
  return (
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
      {showHeader && (
        <div className="flex items-center justify-between px-4 pt-4 pb-2">
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-vpv-text-muted">
              Jornada actual
            </h2>
            <p className="text-lg font-bold text-vpv-text">
              Jornada {data.number}
            </p>
          </div>
          <Link
            href={`/jornadas/${data.number}`}
            className="text-xs text-vpv-accent transition-colors hover:text-vpv-accent-hover"
          >
            Ver completa &rarr;
          </Link>
        </div>
      )}

      <div>
        {data.scores.map((s, i) => (
          <AccordionRow
            key={s.participant_id}
            score={s}
            rank={i + 1}
            seasonId={seasonId}
            matchdayNumber={data.number}
          />
        ))}
      </div>
    </div>
  );
}
