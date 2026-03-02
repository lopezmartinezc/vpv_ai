"use client";

import { PlayerAvatar } from "@/components/ui/player-avatar";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface PitchPlayer {
  player_id: number;
  name: string;
  photo_path: string | null;
  position_slot: string; // "POR", "DEF", "MED", "DEL"
}

interface PitchViewProps {
  formation: string;
  players: PitchPlayer[];
  onRemovePlayer?: (playerId: number) => void;
  className?: string;
}

// ---------------------------------------------------------------------------
// Formation coordinates (% of pitch width/height)
// Converted from backend POSITION_MAP pixel coords (1820x1580 canvas).
// x% = px / 1820 * 100, y% = px / 1580 * 100 (inverted: GK at bottom)
// ---------------------------------------------------------------------------

interface Coord {
  x: number;
  y: number;
}

const FORMATION_COORDS: Record<string, Record<string, Coord[]>> = {
  "1-3-4-3": {
    POR: [{ x: 50, y: 87 }],
    DEF: [
      { x: 15, y: 67 },
      { x: 50, y: 67 },
      { x: 85, y: 67 },
    ],
    MED: [
      { x: 10, y: 42 },
      { x: 37, y: 44 },
      { x: 63, y: 44 },
      { x: 90, y: 42 },
    ],
    DEL: [
      { x: 15, y: 18 },
      { x: 50, y: 18 },
      { x: 85, y: 18 },
    ],
  },
  "1-3-5-2": {
    POR: [{ x: 50, y: 87 }],
    DEF: [
      { x: 15, y: 67 },
      { x: 50, y: 67 },
      { x: 85, y: 67 },
    ],
    MED: [
      { x: 8, y: 40 },
      { x: 28, y: 42 },
      { x: 50, y: 45 },
      { x: 72, y: 42 },
      { x: 92, y: 40 },
    ],
    DEL: [
      { x: 30, y: 18 },
      { x: 70, y: 18 },
    ],
  },
  "1-4-3-3": {
    POR: [{ x: 50, y: 87 }],
    DEF: [
      { x: 10, y: 67 },
      { x: 37, y: 67 },
      { x: 63, y: 67 },
      { x: 90, y: 67 },
    ],
    MED: [
      { x: 15, y: 42 },
      { x: 50, y: 42 },
      { x: 85, y: 42 },
    ],
    DEL: [
      { x: 15, y: 18 },
      { x: 50, y: 18 },
      { x: 85, y: 18 },
    ],
  },
  "1-4-4-2": {
    POR: [{ x: 50, y: 87 }],
    DEF: [
      { x: 10, y: 67 },
      { x: 37, y: 67 },
      { x: 63, y: 67 },
      { x: 90, y: 67 },
    ],
    MED: [
      { x: 10, y: 42 },
      { x: 37, y: 44 },
      { x: 63, y: 44 },
      { x: 90, y: 42 },
    ],
    DEL: [
      { x: 30, y: 18 },
      { x: 70, y: 18 },
    ],
  },
  "1-4-5-1": {
    POR: [{ x: 50, y: 87 }],
    DEF: [
      { x: 10, y: 67 },
      { x: 37, y: 67 },
      { x: 63, y: 67 },
      { x: 90, y: 67 },
    ],
    MED: [
      { x: 8, y: 40 },
      { x: 28, y: 42 },
      { x: 50, y: 45 },
      { x: 72, y: 42 },
      { x: 92, y: 40 },
    ],
    DEL: [{ x: 50, y: 18 }],
  },
  "1-5-3-2": {
    POR: [{ x: 50, y: 87 }],
    DEF: [
      { x: 8, y: 62 },
      { x: 28, y: 64 },
      { x: 50, y: 67 },
      { x: 72, y: 64 },
      { x: 92, y: 62 },
    ],
    MED: [
      { x: 15, y: 40 },
      { x: 50, y: 40 },
      { x: 85, y: 40 },
    ],
    DEL: [
      { x: 30, y: 18 },
      { x: 70, y: 18 },
    ],
  },
  "1-5-4-1": {
    POR: [{ x: 50, y: 87 }],
    DEF: [
      { x: 8, y: 62 },
      { x: 28, y: 64 },
      { x: 50, y: 67 },
      { x: 72, y: 64 },
      { x: 92, y: 62 },
    ],
    MED: [
      { x: 10, y: 40 },
      { x: 37, y: 40 },
      { x: 63, y: 40 },
      { x: 90, y: 40 },
    ],
    DEL: [{ x: 50, y: 18 }],
  },
};

const POSITION_COLORS: Record<string, string> = {
  POR: "bg-amber-500 text-amber-950",
  DEF: "bg-blue-500 text-blue-950",
  MED: "bg-emerald-500 text-emerald-950",
  DEL: "bg-rose-500 text-rose-950",
};

const POSITION_BORDER_COLORS: Record<string, string> = {
  POR: "ring-amber-400",
  DEF: "ring-blue-400",
  MED: "ring-emerald-400",
  DEL: "ring-rose-400",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getSlots(
  formation: string,
): { position: string; coord: Coord; index: number }[] {
  const coords = FORMATION_COORDS[formation];
  if (!coords) return [];

  const slots: { position: string; coord: Coord; index: number }[] = [];
  const order = ["POR", "DEF", "MED", "DEL"] as const;

  for (const pos of order) {
    const posCoords = coords[pos] ?? [];
    posCoords.forEach((coord, i) => {
      slots.push({ position: pos, coord, index: i });
    });
  }

  return slots;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function PitchView({
  formation,
  players,
  onRemovePlayer,
  className = "",
}: PitchViewProps) {
  const slots = getSlots(formation);

  // Map players to slots: for each position, fill slots in order
  const positionQueues: Record<string, PitchPlayer[]> = {
    POR: [],
    DEF: [],
    MED: [],
    DEL: [],
  };
  for (const p of players) {
    positionQueues[p.position_slot]?.push(p);
  }

  return (
    <div
      className={`relative w-full overflow-hidden rounded-xl ${className}`}
      style={{ aspectRatio: "3 / 4" }}
    >
      {/* Football pitch background */}
      <div className="absolute inset-0 bg-gradient-to-b from-green-700 via-green-600 to-green-700">
        {/* Field markings */}
        {/* Outer border */}
        <div className="absolute inset-[4%] rounded-md border-2 border-white/30" />

        {/* Center line */}
        <div className="absolute left-[4%] right-[4%] top-1/2 h-0 -translate-y-1/2 border-t-2 border-white/30" />

        {/* Center circle */}
        <div className="absolute left-1/2 top-1/2 h-[18%] w-[24%] -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white/30" />

        {/* Center dot */}
        <div className="absolute left-1/2 top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-white/40" />

        {/* Top penalty area */}
        <div className="absolute left-[24%] right-[24%] top-[4%] h-[14%] border-2 border-t-0 border-white/30" />

        {/* Top goal area */}
        <div className="absolute left-[36%] right-[36%] top-[4%] h-[7%] border-2 border-t-0 border-white/30" />

        {/* Bottom penalty area */}
        <div className="absolute bottom-[4%] left-[24%] right-[24%] h-[14%] border-2 border-b-0 border-white/30" />

        {/* Bottom goal area */}
        <div className="absolute bottom-[4%] left-[36%] right-[36%] h-[7%] border-2 border-b-0 border-white/30" />
      </div>

      {/* Player slots */}
      {slots.map((slot) => {
        const queue = positionQueues[slot.position];
        const player = queue && queue.length > slot.index ? queue[slot.index] : null;

        return (
          <div
            key={`${slot.position}-${slot.index}`}
            className="absolute -translate-x-1/2 -translate-y-1/2"
            style={{
              left: `${slot.coord.x}%`,
              top: `${slot.coord.y}%`,
            }}
          >
            {player ? (
              <button
                type="button"
                onClick={() => onRemovePlayer?.(player.player_id)}
                className="group flex flex-col items-center gap-0.5"
                title={`Quitar a ${player.name}`}
              >
                <div
                  className={`ring-2 ${POSITION_BORDER_COLORS[slot.position]} rounded-full transition-transform group-hover:scale-110 group-active:scale-95`}
                >
                  <PlayerAvatar
                    photoPath={player.photo_path}
                    name={player.name}
                    size={44}
                  />
                </div>
                <span className="max-w-[72px] truncate rounded bg-black/60 px-1 py-0.5 text-[10px] font-medium leading-tight text-white">
                  {player.name.split(" ").pop()}
                </span>
              </button>
            ) : (
              <div className="flex flex-col items-center gap-0.5">
                <div className="flex h-[44px] w-[44px] items-center justify-center rounded-full border-2 border-dashed border-white/40 bg-white/10">
                  <span
                    className={`rounded px-1 py-0.5 text-[9px] font-bold ${POSITION_COLORS[slot.position]}`}
                  >
                    {slot.position}
                  </span>
                </div>
                <span className="h-4" />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
