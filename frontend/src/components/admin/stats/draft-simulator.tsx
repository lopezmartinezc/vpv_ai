"use client";

import { useMemo, useState } from "react";

import { POS_COLOR } from "@/components/admin/stats/common";
import { BIG_TEAMS, ROSTER_TARGET, simulateDraft } from "@/lib/draft-simulator";
import type { DraftValuePlayer } from "@/types";

const POSITIONS = ["POR", "DEF", "MED", "DEL"] as const;

function isBig(team: string) {
  return BIG_TEAMS.some((t) => team.includes(t));
}

/**
 * Runs a whole draft against bots that behave like this league does, so you can
 * see what actually falls to you from a given slot before the real thing.
 * Nothing is saved: it is a sandbox over the board already on screen.
 */
export function DraftSimulator({
  players,
  participantCount,
}: {
  players: DraftValuePlayer[];
  participantCount: number;
}) {
  const [participants, setParticipants] = useState(
    participantCount > 0 ? participantCount : 11,
  );
  const [myPosition, setMyPosition] = useState(1);
  const [rounds, setRounds] = useState(26);
  const [bigTeamBias, setBigTeamBias] = useState(0.2);
  const [myOrder, setMyOrder] = useState<"priority" | "vorp">("priority");
  const [seed, setSeed] = useState(1);
  const [view, setView] = useState<"mine" | "all">("mine");

  const result = useMemo(
    () =>
      simulateDraft(players, {
        participants,
        myPosition: Math.min(myPosition, participants),
        rounds,
        seed,
        bigTeamBias,
        myOrder,
      }),
    [players, participants, myPosition, rounds, seed, bigTeamBias, myOrder],
  );

  const mySquad = result.squads.find((s) => s.isMe);
  const myCounts = useMemo(() => {
    const out: Record<string, number> = {};
    for (const pos of POSITIONS) {
      out[pos] = mySquad?.players.filter((p) => p.position === pos).length ?? 0;
    }
    return out;
  }, [mySquad]);

  return (
    <details className="rounded-lg border border-vpv-card-border bg-vpv-card">
      <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-vpv-text">
        Simulador de draft
        <span className="ml-2 text-xs font-normal text-vpv-text-muted">
          ¿qué me llega si elijo en la posición N?
        </span>
      </summary>

      <div className="space-y-4 border-t border-vpv-card-border px-4 py-4">
        <p className="text-xs text-vpv-text-muted">
          Los rivales no siguen el tablero: imitan cómo se draftea en esta liga —
          un portero de los tres grandes sale en la primera ronda, quien lo coge
          reserva el hueco para su suplente, y todos sobrevaloran a los jugadores
          de Madrid, Barça y Atlético. Tú sigues el orden que elijas. No se guarda
          nada.
        </p>

        <div className="flex flex-wrap items-end gap-3 text-xs">
          <label className="flex flex-col gap-1">
            <span className="text-vpv-text-muted">Participantes</span>
            <input
              type="number"
              min={2}
              max={20}
              value={participants}
              onChange={(e) => setParticipants(Number(e.target.value) || 2)}
              className="w-20 rounded-md border border-vpv-card-border bg-vpv-bg px-2 py-1 text-vpv-text"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-vpv-text-muted">Mi posición</span>
            <input
              type="number"
              min={1}
              max={participants}
              value={myPosition}
              onChange={(e) => setMyPosition(Number(e.target.value) || 1)}
              className="w-20 rounded-md border border-vpv-card-border bg-vpv-bg px-2 py-1 text-vpv-text"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-vpv-text-muted">Rondas</span>
            <input
              type="number"
              min={1}
              max={30}
              value={rounds}
              onChange={(e) => setRounds(Number(e.target.value) || 1)}
              className="w-20 rounded-md border border-vpv-card-border bg-vpv-bg px-2 py-1 text-vpv-text"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-vpv-text-muted">Mi orden</span>
            <select
              value={myOrder}
              onChange={(e) => setMyOrder(e.target.value as "priority" | "vorp")}
              className="rounded-md border border-vpv-card-border bg-vpv-bg px-2 py-1 text-vpv-text"
            >
              <option value="priority">Prioridad</option>
              <option value="vorp">VORP</option>
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-vpv-text-muted">
              Sesgo equipo grande: {Math.round(bigTeamBias * 100)}%
            </span>
            <input
              type="range"
              min={0}
              max={60}
              value={bigTeamBias * 100}
              onChange={(e) => setBigTeamBias(Number(e.target.value) / 100)}
              className="w-40"
            />
          </label>
          <button
            type="button"
            onClick={() => setSeed((s) => s + 1)}
            className="rounded-md bg-vpv-accent px-3 py-1.5 font-medium text-white"
          >
            Otro draft
          </button>
        </div>

        {result.exhausted && (
          <p className="rounded-md bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
            El tablero se quedó sin jugadores elegibles antes de acabar. Baja las
            rondas o los participantes: el resultado está incompleto.
          </p>
        )}

        <div className="flex gap-2 text-xs">
          {(["mine", "all"] as const).map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => setView(v)}
              className={
                v === view
                  ? "rounded-md bg-vpv-accent px-3 py-1 font-medium text-white"
                  : "rounded-md border border-vpv-card-border px-3 py-1 text-vpv-text-muted"
              }
            >
              {v === "mine" ? "Mi plantilla" : "Draft completo"}
            </button>
          ))}
        </div>

        {view === "mine" ? (
          <div className="space-y-3">
            <div className="flex flex-wrap gap-3 text-xs">
              {POSITIONS.map((pos) => (
                <span key={pos} className="text-vpv-text-muted">
                  <span className={POS_COLOR[pos]}>{pos}</span>{" "}
                  <span className="font-medium text-vpv-text">{myCounts[pos]}</span>
                  <span className="opacity-60"> / {ROSTER_TARGET[pos]}</span>
                </span>
              ))}
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="text-vpv-text-muted">
                  <tr>
                    <th className="px-2 py-1 text-left">Pick</th>
                    <th className="px-2 py-1 text-left">R</th>
                    <th className="px-2 py-1 text-left">Jugador</th>
                    <th className="px-2 py-1 text-left">Pos</th>
                    <th className="px-2 py-1 text-left">Equipo</th>
                    <th className="px-2 py-1 text-right">Prio</th>
                    <th className="px-2 py-1 text-right">VORP</th>
                  </tr>
                </thead>
                <tbody>
                  {result.myPicks.map((pick) => (
                    <tr key={pick.pickNumber} className="border-t border-vpv-card-border">
                      <td className="px-2 py-1 text-vpv-text-muted">#{pick.pickNumber}</td>
                      <td className="px-2 py-1 text-vpv-text-muted">{pick.round}</td>
                      <td className="px-2 py-1 text-vpv-text">{pick.player.display_name}</td>
                      <td className={`px-2 py-1 ${POS_COLOR[pick.player.position] ?? ""}`}>
                        {pick.player.position}
                      </td>
                      <td className="px-2 py-1 text-vpv-text-muted">
                        {pick.player.team_name}
                        {isBig(pick.player.team_name) ? " ★" : ""}
                      </td>
                      <td className="px-2 py-1 text-right text-vpv-text">
                        {pick.player.priority?.toFixed(1) ?? "-"}
                      </td>
                      <td className="px-2 py-1 text-right text-vpv-text-muted">
                        {pick.player.vorp?.toFixed(2) ?? "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div className="max-h-96 overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-vpv-card text-vpv-text-muted">
                <tr>
                  <th className="px-2 py-1 text-left">Pick</th>
                  <th className="px-2 py-1 text-left">R</th>
                  <th className="px-2 py-1 text-left">Elige</th>
                  <th className="px-2 py-1 text-left">Jugador</th>
                  <th className="px-2 py-1 text-left">Pos</th>
                  <th className="px-2 py-1 text-left">Equipo</th>
                </tr>
              </thead>
              <tbody>
                {result.picks.map((pick) => (
                  <tr
                    key={pick.pickNumber}
                    className={`border-t border-vpv-card-border ${
                      pick.isMe ? "bg-vpv-accent/10" : ""
                    }`}
                  >
                    <td className="px-2 py-1 text-vpv-text-muted">#{pick.pickNumber}</td>
                    <td className="px-2 py-1 text-vpv-text-muted">{pick.round}</td>
                    <td className="px-2 py-1 text-vpv-text-muted">
                      {pick.isMe ? "YO" : `P${pick.participantId}`}
                    </td>
                    <td className="px-2 py-1 text-vpv-text">{pick.player.display_name}</td>
                    <td className={`px-2 py-1 ${POS_COLOR[pick.player.position] ?? ""}`}>
                      {pick.player.position}
                    </td>
                    <td className="px-2 py-1 text-vpv-text-muted">
                      {pick.player.team_name}
                      {isBig(pick.player.team_name) ? " ★" : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </details>
  );
}
