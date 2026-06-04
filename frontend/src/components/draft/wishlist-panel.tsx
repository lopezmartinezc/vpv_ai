"use client";

import { useCallback, useEffect, useState } from "react";
import {
  DndContext,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

import { PlayerAvatar } from "@/components/ui/player-avatar";
import { apiClient } from "@/lib/api-client";
import type { PlayerSearchItem, Wishlist, WishlistPlayerItem } from "@/types";

const POS_COLORS: Record<string, string> = {
  POR: "bg-amber-600/20 text-amber-400",
  DEF: "bg-blue-600/20 text-blue-400",
  MED: "bg-green-600/20 text-green-400",
  DEL: "bg-red-600/20 text-red-400",
};

const MAX_ITEMS = 50;

interface WishlistPanelProps {
  draftId: number;
  /**
   * Incremented by the parent every time a `pick_added` / `pick_deleted`
   * event arrives — used to refresh `is_already_picked` flags without a
   * full page reload.
   */
  refreshKey: number;
}

export function WishlistPanel({ draftId, refreshKey }: WishlistPanelProps) {
  const [wishlist, setWishlist] = useState<Wishlist | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);

  const [search, setSearch] = useState("");
  const [posFilter, setPosFilter] = useState("");
  const [searchResults, setSearchResults] = useState<PlayerSearchItem[]>([]);
  const [searching, setSearching] = useState(false);

  const fetchWishlist = useCallback(async () => {
    try {
      const data = await apiClient.get<Wishlist>(`/drafts/${draftId}/wishlist`);
      setWishlist(data);
      setDirty(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error cargando wishlist");
    } finally {
      setLoading(false);
    }
  }, [draftId]);

  useEffect(() => {
    setLoading(true);
    fetchWishlist();
  }, [fetchWishlist]);

  // Re-fetch on every external pick so is_already_picked stays accurate.
  // Skip refetch when there are unsaved local edits to avoid clobbering them.
  useEffect(() => {
    if (refreshKey === 0 || dirty) return;
    fetchWishlist();
  }, [refreshKey, dirty, fetchWishlist]);

  useEffect(() => {
    if (!search.trim() && !posFilter) {
      setSearchResults([]);
      return;
    }
    const timeout = setTimeout(async () => {
      setSearching(true);
      try {
        const params = new URLSearchParams();
        if (search.trim()) params.set("q", search.trim());
        if (posFilter) params.set("position", posFilter);
        const res = await apiClient.get<{ players: PlayerSearchItem[] }>(
          `/drafts/${draftId}/players/search?${params}`,
        );
        const existingIds = new Set((wishlist?.players ?? []).map((p) => p.player_id));
        setSearchResults(
          res.players.filter((p) => !p.is_already_picked && !existingIds.has(p.id)),
        );
      } catch {
        setSearchResults([]);
      } finally {
        setSearching(false);
      }
    }, 300);
    return () => clearTimeout(timeout);
  }, [search, posFilter, draftId, wishlist?.players]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
  );

  function addPlayer(p: PlayerSearchItem) {
    if (!wishlist) return;
    if (wishlist.players.length >= MAX_ITEMS) {
      setError(`Máximo ${MAX_ITEMS} jugadores`);
      return;
    }
    const newItem: WishlistPlayerItem = {
      player_id: p.id,
      display_name: p.display_name,
      position: p.position,
      team_name: p.team_name,
      photo_path: p.photo_path,
      is_already_picked: false,
      priority: wishlist.players.length,
    };
    setWishlist({ ...wishlist, players: [...wishlist.players, newItem] });
    setDirty(true);
    setSearch("");
    setSearchResults([]);
  }

  function removePlayer(playerId: number) {
    if (!wishlist) return;
    const next = wishlist.players
      .filter((p) => p.player_id !== playerId)
      .map((p, i) => ({ ...p, priority: i }));
    setWishlist({ ...wishlist, players: next });
    setDirty(true);
  }

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id || !wishlist) return;
    const oldIndex = wishlist.players.findIndex((p) => p.player_id === Number(active.id));
    const newIndex = wishlist.players.findIndex((p) => p.player_id === Number(over.id));
    if (oldIndex < 0 || newIndex < 0) return;
    const reordered = arrayMove(wishlist.players, oldIndex, newIndex).map((p, i) => ({
      ...p,
      priority: i,
    }));
    setWishlist({ ...wishlist, players: reordered });
    setDirty(true);
  }

  async function toggleEnabled() {
    if (!wishlist) return;
    const next = !wishlist.enabled;
    setWishlist({ ...wishlist, enabled: next });
    try {
      const updated = await apiClient.post<Wishlist>(
        `/drafts/${draftId}/wishlist/toggle`,
        { enabled: next },
      );
      setWishlist(updated);
      setDirty(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al cambiar estado");
      // Revert
      setWishlist({ ...wishlist, enabled: !next });
    }
  }

  async function save() {
    if (!wishlist) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await apiClient.put<Wishlist>(`/drafts/${draftId}/wishlist`, {
        enabled: wishlist.enabled,
        player_ids: wishlist.players.map((p) => p.player_id),
      });
      setWishlist(updated);
      setDirty(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al guardar");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <p className="text-center text-xs text-vpv-text-muted">Cargando wishlist…</p>
    );
  }

  if (!wishlist) {
    return null;
  }

  // Already-picked players stay in `wishlist.players` (and in the DB) so
  // the admin can undo a pick without losing the configured priority,
  // but we don't render them — they would just be greyed-out clutter
  // since the auto-pick engine skips them anyway.
  const visiblePlayers = wishlist.players.filter((p) => !p.is_already_picked);
  const visibleIds = visiblePlayers.map((p) => p.player_id.toString());
  const hiddenCount = wishlist.players.length - visiblePlayers.length;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <label className="flex items-center gap-2 text-xs text-vpv-text">
          <input
            type="checkbox"
            checked={wishlist.enabled}
            onChange={toggleEnabled}
            className="h-4 w-4 accent-vpv-accent"
          />
          Auto-pick activo
        </label>
        <button
          type="button"
          onClick={save}
          disabled={!dirty || saving}
          className="rounded-lg bg-vpv-accent px-3 py-1 text-xs font-medium text-vpv-bg transition-opacity disabled:opacity-40"
        >
          {saving ? "Guardando…" : dirty ? "Guardar" : "Guardado"}
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-400">
          {error}
        </div>
      )}

      <p className="text-[11px] text-vpv-text-muted">
        Cuando llegue tu turno, se elegirá automáticamente al jugador con más
        prioridad que siga disponible. Arrastra para reordenar.
      </p>

      <div className="flex flex-wrap gap-2">
        <input
          type="text"
          placeholder="Buscar para añadir…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="min-w-0 flex-1 rounded-lg border border-vpv-border bg-vpv-bg px-3 py-1.5 text-sm text-vpv-text placeholder:text-vpv-text-muted/50 focus:border-vpv-accent focus:outline-none"
        />
        <select
          value={posFilter}
          onChange={(e) => setPosFilter(e.target.value)}
          className="rounded-lg border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
        >
          <option value="">Pos</option>
          {["POR", "DEF", "MED", "DEL"].map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
      </div>

      {searching && (
        <p className="text-center text-xs text-vpv-text-muted">Buscando…</p>
      )}

      {searchResults.length > 0 && (
        <div className="max-h-48 space-y-1 overflow-y-auto rounded-lg border border-vpv-border bg-vpv-bg p-1">
          {searchResults.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => addPlayer(p)}
              className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm transition-colors hover:bg-vpv-accent/20"
            >
              <PlayerAvatar photoPath={p.photo_path} name={p.display_name} size={24} />
              <span
                className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${POS_COLORS[p.position] ?? ""}`}
              >
                {p.position}
              </span>
              <span className="flex-1 truncate text-vpv-text">{p.display_name}</span>
              <span className="text-xs text-vpv-text-muted">{p.team_name}</span>
            </button>
          ))}
        </div>
      )}

      <div>
        <p className="mb-1 text-[11px] uppercase tracking-wide text-vpv-text-muted">
          Mi lista ({visiblePlayers.length}/{MAX_ITEMS})
          {hiddenCount > 0 && (
            <span className="ml-1 normal-case text-vpv-text-muted/60">
              · {hiddenCount} ya elegido{hiddenCount === 1 ? "" : "s"} oculto{hiddenCount === 1 ? "" : "s"}
            </span>
          )}
        </p>
        {visiblePlayers.length === 0 ? (
          <p className="rounded-lg border border-dashed border-vpv-border px-3 py-4 text-center text-xs text-vpv-text-muted">
            {wishlist.players.length === 0
              ? "Aún no has añadido jugadores."
              : "Todos los jugadores de tu lista ya fueron elegidos. Añade más para futuras rondas."}
          </p>
        ) : (
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
            <SortableContext items={visibleIds} strategy={verticalListSortingStrategy}>
              <div className="space-y-1">
                {visiblePlayers.map((p, idx) => (
                  <SortableWishlistRow
                    key={p.player_id}
                    item={p}
                    priorityLabel={idx + 1}
                    onRemove={() => removePlayer(p.player_id)}
                  />
                ))}
              </div>
            </SortableContext>
          </DndContext>
        )}
      </div>
    </div>
  );
}

function SortableWishlistRow({
  item,
  priorityLabel,
  onRemove,
}: {
  item: WishlistPlayerItem;
  priorityLabel: number;
  onRemove: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: item.player_id.toString() });

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : item.is_already_picked ? 0.4 : 1,
    touchAction: "none",
  };

  const posClass = item.position ? POS_COLORS[item.position] ?? "" : "";

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="flex items-center gap-2 rounded-lg border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm select-none"
    >
      <button
        type="button"
        {...attributes}
        {...listeners}
        aria-label="Arrastrar para reordenar"
        className="cursor-grab px-1 text-vpv-text-muted/60 hover:text-vpv-text active:cursor-grabbing"
      >
        ⋮⋮
      </button>
      <span className="w-6 text-center text-xs font-semibold tabular-nums text-vpv-text-muted">
        {priorityLabel}
      </span>
      <PlayerAvatar photoPath={item.photo_path} name={item.display_name} size={24} />
      {item.position && (
        <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${posClass}`}>
          {item.position}
        </span>
      )}
      <span className="min-w-0 flex-1 truncate text-vpv-text">{item.display_name}</span>
      {item.team_name && (
        <span className="hidden text-xs text-vpv-text-muted sm:inline">
          {item.team_name}
        </span>
      )}
      {item.is_already_picked && (
        <span className="rounded bg-vpv-text-muted/20 px-1.5 py-0.5 text-[10px] text-vpv-text-muted">
          ya elegido
        </span>
      )}
      <button
        type="button"
        onClick={onRemove}
        aria-label={`Quitar ${item.display_name}`}
        className="ml-1 inline-flex h-6 w-6 items-center justify-center rounded text-vpv-text-muted transition-colors hover:bg-red-500/15 hover:text-red-500"
      >
        ✕
      </button>
    </div>
  );
}
