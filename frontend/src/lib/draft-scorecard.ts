/**
 * Shared UI constants for draft scorecard rendering.
 *
 * The backend's scorecard (backend/src/features/stats/scorecard.py) tags
 * players with a position-aware tier, a buy/sell signal, and a few
 * warning flags. These constants render those tags consistently across:
 *   - the live draft (admin overlay)
 *   - the Draft Retro analytics tab
 *
 * Keep this module dependency-free so it can be imported from any
 * component or page.
 */

export type ScorecardTier = "elite" | "solid" | "normal" | "weak";

export type ScorecardSignal = "strong_buy" | "buy" | "hold" | "avoid";

export const TIER_COLORS: Record<string, string> = {
  elite: "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30",
  solid: "bg-blue-500/15 text-blue-300 border border-blue-500/30",
  normal: "bg-zinc-500/15 text-zinc-300 border border-zinc-500/30",
  weak: "bg-red-500/15 text-red-300 border border-red-500/30",
};

export const TIER_LABELS: Record<string, string> = {
  elite: "Elite",
  solid: "Sólido",
  normal: "Normal",
  weak: "Flojo",
};

export const SIGNAL_LABELS: Record<string, { label: string; classes: string }> = {
  strong_buy: {
    label: "⭐ STRONG BUY",
    classes: "bg-amber-500/20 text-amber-300 border border-amber-500/40",
  },
  buy: {
    label: "🟢 BUY",
    classes: "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30",
  },
  hold: {
    label: "🔵 HOLD",
    classes: "bg-blue-500/10 text-blue-300 border border-blue-500/20",
  },
  avoid: {
    label: "🔴 AVOID",
    classes: "bg-red-500/15 text-red-300 border border-red-500/30",
  },
};

/** Position chip colors used across draft + stats pages. */
export const POSITION_COLORS: Record<string, string> = {
  POR: "bg-amber-600/20 text-amber-400",
  DEF: "bg-blue-600/20 text-blue-400",
  MED: "bg-green-600/20 text-green-400",
  DEL: "bg-red-600/20 text-red-400",
};

/** Hex strokes for the scatter plot — readable on dark theme. */
export const POSITION_HEX: Record<string, string> = {
  POR: "#f59e0b", // amber
  DEF: "#3b82f6", // blue
  MED: "#22c55e", // green
  DEL: "#ef4444", // red
};

/** Tag chip colors for draft retrospective. */
export const TAG_COLORS: Record<string, string> = {
  steal: "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30",
  bust: "bg-red-500/15 text-red-300 border border-red-500/30",
  normal: "bg-zinc-500/15 text-zinc-300 border border-zinc-500/30",
};

export const TAG_LABELS: Record<string, string> = {
  steal: "💎 Steal",
  bust: "⚠️ Bust",
  normal: "—",
};
