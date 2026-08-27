"use client";

/**
 * RosterCounter — live composition of a participant's drafted squad vs their
 * OWN target. Each user personalizes the target (persisted per browser); the
 * recommended split (from the strategy analysis) is the default and shown as a
 * hint. Forwards are the position most people under-draft, so it flags when
 * you're falling behind on them relative to your target.
 */
import { useEffect, useState } from "react";

const ORDER = ["POR", "DEF", "MED", "DEL"] as const;
type Pos = (typeof ORDER)[number];
type Targets = Record<Pos, number>;

// Recommended split (26): forwards are the most under-drafted position.
const RECOMMENDED: Targets = { POR: 2, DEF: 8, MED: 7, DEL: 6 };
const STORAGE_KEY = "vpv-roster-target";
const ROSTER_SIZE = 26;

const POS_COLOR: Record<string, string> = {
  POR: "bg-amber-500/20 text-amber-400",
  DEF: "bg-blue-500/20 text-blue-400",
  MED: "bg-emerald-500/20 text-emerald-400",
  DEL: "bg-rose-500/20 text-rose-400",
};

function sanitize(raw: unknown): Targets {
  const out: Targets = { ...RECOMMENDED };
  if (raw && typeof raw === "object") {
    for (const p of ORDER) {
      const v = (raw as Record<string, unknown>)[p];
      if (typeof v === "number" && Number.isFinite(v)) {
        out[p] = Math.max(0, Math.min(ROSTER_SIZE, Math.round(v)));
      }
    }
  }
  return out;
}

export function RosterCounter({ positions }: { positions: string[] }) {
  const [targets, setTargets] = useState<Targets>(RECOMMENDED);
  const [editing, setEditing] = useState(false);

  // Load the user's saved target (per browser) after mount. Deferred via
  // queueMicrotask so the setState isn't synchronous in the effect body
  // (React 19 flags that) and to avoid an SSR/hydration mismatch.
  useEffect(() => {
    let cancelled = false;
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = sanitize(JSON.parse(raw));
        queueMicrotask(() => {
          if (!cancelled) setTargets(parsed);
        });
      }
    } catch {
      /* private mode / blocked storage → keep the recommended default */
    }
    return () => {
      cancelled = true;
    };
  }, []);

  function update(pos: Pos, val: number) {
    const next = { ...targets, [pos]: Math.max(0, Math.min(ROSTER_SIZE, val)) };
    setTargets(next);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      /* ignore */
    }
  }

  function reset() {
    setTargets(RECOMMENDED);
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
  }

  const counts: Record<string, number> = {};
  for (const p of positions) counts[p] = (counts[p] ?? 0) + 1;
  const total = positions.length;
  const isCustom = ORDER.some((p) => targets[p] !== RECOMMENDED[p]);

  // Behind on forwards if you have fewer than your own target's pace implies.
  const delCount = counts["DEL"] ?? 0;
  const behindOnForwards =
    total >= 6 &&
    targets.DEL > 0 &&
    delCount < Math.floor((total * targets.DEL) / ROSTER_SIZE) &&
    delCount < targets.DEL;

  return (
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card px-4 py-2.5">
      <div className="mb-1.5 flex items-baseline justify-between">
        <h4 className="text-xs font-semibold text-vpv-text">Tu plantilla</h4>
        <div className="flex items-center gap-2">
          <span className="text-[11px] tabular-nums text-vpv-text-muted">
            {total}/{ROSTER_SIZE}
          </span>
          <button
            onClick={() => setEditing((v) => !v)}
            className="text-[10px] text-vpv-accent hover:underline"
          >
            {editing ? "Hecho" : "Editar objetivos"}
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {ORDER.map((pos) => {
          const c = counts[pos] ?? 0;
          const met = c >= targets[pos];
          return (
            <div
              key={pos}
              className="flex items-center gap-1.5 rounded border border-vpv-border bg-vpv-bg px-2 py-1"
              title={`recomendado ${RECOMMENDED[pos]}`}
            >
              <span className={`rounded px-1 py-0.5 text-[9px] font-medium ${POS_COLOR[pos]}`}>
                {pos}
              </span>
              <span
                className={`text-sm font-bold tabular-nums ${met ? "text-emerald-400" : "text-vpv-text"}`}
              >
                {c}
              </span>
              {editing ? (
                <input
                  type="number"
                  min={0}
                  max={ROSTER_SIZE}
                  value={targets[pos]}
                  onChange={(e) => update(pos, Number(e.target.value))}
                  className="w-10 rounded border border-vpv-border bg-vpv-card px-1 py-0.5 text-xs tabular-nums text-vpv-text"
                  aria-label={`Objetivo ${pos}`}
                />
              ) : (
                <span className="text-[10px] text-vpv-text-muted">/{targets[pos]}</span>
              )}
            </div>
          );
        })}
        {editing && isCustom && (
          <button
            onClick={reset}
            className="text-[10px] text-vpv-text-muted hover:text-vpv-text hover:underline"
          >
            Restablecer recomendado
          </button>
        )}
      </div>

      {behindOnForwards && !editing && (
        <p className="mt-1.5 text-[11px] text-amber-400">
          ⚠ Vas corto de delanteros — la mejor formación (1-4-3-3) pide 3 y hace falta fondo.
        </p>
      )}
      {editing && (
        <p className="mt-1.5 text-[10px] text-vpv-text-muted">
          Recomendado: 2 POR · 8 DEF · 7-8 MED · 6-7 DEL. Ajústalo a tu estrategia.
        </p>
      )}
    </div>
  );
}
