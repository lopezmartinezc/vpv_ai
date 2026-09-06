/**
 * Canonical admin player tags for the draft (single source of truth).
 *
 * Used by the draft board (`components/admin/stats/draft-value-tab.tsx`) to
 * edit them and by the live-draft admin UI to render them, so labels/colours
 * never drift. The backend allowed set + multipliers live in
 * `stats/service_draft.py` (ALLOWED_TAGS / TAG_MULTIPLIER).
 */
export const PLAYER_TAGS: { key: string; label: string; cls: string }[] = [
  { key: "titular", label: "Titular", cls: "bg-green-500/20 text-green-300" },
  { key: "suplente", label: "Suplente", cls: "bg-amber-500/15 text-amber-300" },
  { key: "penaltis", label: "Penaltis", cls: "bg-emerald-500/15 text-emerald-300" },
  { key: "gol", label: "Gol", cls: "bg-lime-500/15 text-lime-300" },
  { key: "lesion", label: "Lesión", cls: "bg-red-500/20 text-red-300" },
  { key: "objetivo", label: "Objetivo", cls: "bg-blue-500/20 text-blue-300" },
  { key: "evitar", label: "Evitar", cls: "bg-red-500/10 text-red-400" },
];

export const PLAYER_TAG_LABELS: Record<string, string> = Object.fromEntries(
  PLAYER_TAGS.map((t) => [t.key, t.label]),
);
export const PLAYER_TAG_CLASSES: Record<string, string> = Object.fromEntries(
  PLAYER_TAGS.map((t) => [t.key, t.cls]),
);

/** Small emoji per tag, for compact rows where a full chip doesn't fit. */
export const PLAYER_TAG_EMOJI: Record<string, string> = {
  titular: "⭐",
  gol: "🥅",
  penaltis: "⚽",
  objetivo: "🎯",
  evitar: "🚫",
  lesion: "🚑",
  suplente: "🪑",
};
