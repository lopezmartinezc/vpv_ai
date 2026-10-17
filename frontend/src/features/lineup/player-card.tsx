"use client";

import type { JSX } from "react";
import { PlayerAvatar } from "@/components/ui/player-avatar";
import { SourceBadges, type SourceCoverage, type SourceReading } from "@/components/lineup/lineup-intel";
import {
  DIFFICULTY_STYLE,
  difficultyTitle,
  fixtureDifficulty,
  type OpponentStrength,
} from "@/lib/fixture-difficulty";
import { POSITION_COLORS, type Position } from "@/features/lineup/positions";
import type { PlayerPrediction, PlayerRecentForm, SquadPlayerEntry } from "@/types";

const RESULT_BG: Record<number, string> = {
  2: "bg-emerald-500",
  1: "bg-amber-400",
  0: "bg-red-500",
};

function FormIndicator({ form }: { form: PlayerRecentForm }): JSX.Element {
  return (
    <div className="flex items-center gap-[3px]">
      {form.matches.map((m, i) => (
        <div
          key={i}
          className="flex flex-col items-center gap-px"
          title={
            m.played
              ? `${m.result === 2 ? "Victoria" : m.result === 1 ? "Empate" : "Derrota"} ${m.is_home ? "(Casa)" : "(Fuera)"} — ${m.points} pts`
              : "No jugo"
          }
        >
          <div
            className={`flex h-4 w-4 items-center justify-center rounded-sm text-[8px] font-bold leading-none ${
              m.played
                ? `${RESULT_BG[m.result] ?? "bg-red-500"} text-white`
                : "border border-dashed border-vpv-border text-vpv-text-muted/30"
            }`}
          >
            {m.played ? m.points : "-"}
          </div>
          {m.played && (
            <span className="text-[7px] leading-none text-vpv-text-muted/50">
              {m.is_home ? "C" : "F"}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

function StatBadge({
  icon,
  value,
  title,
  color = "text-vpv-text-muted",
}: {
  icon: string;
  value: number;
  title: string;
  color?: string;
}): JSX.Element | null {
  if (value === 0) return null;
  return (
    <span
      className={`inline-flex items-center gap-px ${color}`}
      title={title}
    >
      <span className="text-[9px]">{icon}</span>
      <span className="tabular-nums">{value}</span>
    </span>
  );
}

function PlayerFormStats({
  form,
  position,
}: {
  form: PlayerRecentForm;
  position: string;
}): JSX.Element {
  const isDef = position === "POR" || position === "DEF";
  const totalGoals = form.goals + form.penalty_goals;

  return (
    <div className="flex items-center gap-1.5 text-[10px]">
      {isDef && (
        <StatBadge icon={"\uD83D\uDEE1\uFE0F"} value={form.clean_sheets} title="Imbatibilidades" color="text-sky-400" />
      )}
      <StatBadge icon={"\u26BD"} value={totalGoals} title="Goles" color="text-vpv-text-muted" />
      <StatBadge icon={"\uD83C\uDFAF"} value={form.assists} title="Asistencias" color="text-vpv-text-muted" />
      <StatBadge icon={"\uD83D\uDFE8"} value={form.yellow_cards} title="Tarjetas" color="text-yellow-400" />
    </div>
  );
}

const TREND_ICONS: Record<string, string> = {
  rising: "\u2197",   // ↗
  stable: "\u2192",   // →
  falling: "\u2198",  // ↘
};

const TREND_COLORS: Record<string, string> = {
  rising: "text-emerald-400",
  stable: "text-vpv-text-muted",
  falling: "text-red-400",
};

export function PlayerCard({
  player,
  isSelected,
  isDisabled,
  onToggle,
  showPoints = false,
  prediction,
  fixture,
  readings,
  coverage,
}: {
  player: SquadPlayerEntry;
  isSelected: boolean;
  isDisabled: boolean;
  onToggle: (player: SquadPlayerEntry) => void;
  showPoints?: boolean;
  prediction?: PlayerPrediction;
  fixture?: OpponentStrength;
  readings?: SourceReading[];
  coverage?: SourceCoverage[];
}): JSX.Element {
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
          {player.opponent_team_name && (
            <>
              <span className="mx-1 text-vpv-text-muted/40">·</span>
              <span
                className={
                  player.is_home
                    ? "text-emerald-400"
                    : "text-amber-400"
                }
                title={player.is_home ? "Local" : "Visitante"}
              >
                {player.is_home ? "vs" : "@"} {player.opponent_team_name}
              </span>
              {(() => {
                const grade = fixtureDifficulty(player.position, fixture);
                if (!grade || !fixture) return null;
                return (
                  <span
                    className={`ml-1.5 rounded px-1 py-px text-[9px] font-medium ${DIFFICULTY_STYLE[grade]}`}
                    title={difficultyTitle(player.position, fixture, grade)}
                  >
                    {grade === "facil" ? "fácil" : grade === "dificil" ? "difícil" : "media"}
                  </span>
                );
              })()}
            </>
          )}
        </p>
        {player.recent_form && player.recent_form.matches.length > 0 && (
          <div className="mt-0.5 flex items-center gap-2">
            <FormIndicator form={player.recent_form} />
            <PlayerFormStats
              form={player.recent_form}
              position={player.position}
            />
          </div>
        )}
        {prediction && (
          <div className="mt-0.5 flex items-center gap-2 text-[10px]">
            <span
              className="font-bold text-vpv-accent tabular-nums"
              title={`Puntos esperados · ${prediction.xpts_if_plays.toFixed(1)} si juega`}
            >
              xPts {prediction.xpts.toFixed(1)}
            </span>
            <span className="text-vpv-text-muted" title={prediction.is_home ? "Casa" : "Fuera"}>
              vs {prediction.opponent_name} ({prediction.is_home ? "C" : "F"})
            </span>
            <span className="text-vpv-text-muted tabular-nums" title="Probabilidad de titular">
              {Math.round(prediction.starter_pct)}%
            </span>
            <span className={TREND_COLORS[prediction.trend] ?? "text-vpv-text-muted"} title={`Tendencia: ${prediction.trend}`}>
              {TREND_ICONS[prediction.trend] ?? "→"}
            </span>
          </div>
        )}
        <SourceBadges readings={readings} coverage={coverage} />
      </div>

      <div className="flex shrink-0 flex-col items-end gap-0.5">
        <span
          className={`rounded border px-1.5 py-0.5 text-[10px] font-bold ${POSITION_COLORS[pos]}`}
        >
          {pos}
        </span>
        {showPoints && (
          <span className="text-xs tabular-nums text-vpv-text-muted">
            {player.season_points} pts
          </span>
        )}
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
