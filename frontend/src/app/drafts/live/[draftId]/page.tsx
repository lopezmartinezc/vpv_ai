"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import { useDraftWebSocket } from "@/hooks/use-draft-websocket";
import { apiClient } from "@/lib/api-client";
import { PlayerAvatar } from "@/components/ui/player-avatar";
import type { DraftDetailResponse, DraftPickEntry } from "@/types";

interface PlayerSearchItem {
  id: number;
  display_name: string;
  position: string;
  team_name: string;
  photo_path: string | null;
  is_already_picked: boolean;
}

interface MeResponse {
  id: number;
  username: string;
  display_name: string;
  email: string | null;
  is_admin: boolean;
  is_draft_manager: boolean;
}

const POS_COLORS: Record<string, string> = {
  POR: "bg-amber-600/20 text-amber-400",
  DEF: "bg-blue-600/20 text-blue-400",
  MED: "bg-green-600/20 text-green-400",
  DEL: "bg-red-600/20 text-red-400",
};

export default function LiveDraftPage() {
  const { draftId: draftIdParam } = useParams<{ draftId: string }>();
  const draftId = Number(draftIdParam);
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const { selectedSeason } = useSeason();
  const { data: me } = useFetch<MeResponse>(user ? "/auth/me" : null);

  const [draft, setDraft] = useState<DraftDetailResponse | null>(null);
  const [picks, setPicks] = useState<DraftPickEntry[]>([]);
  const [nextParticipantId, setNextParticipantId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Player search
  const [search, setSearch] = useState("");
  const [posFilter, setPosFilter] = useState<string>("");
  const [searchResults, setSearchResults] = useState<PlayerSearchItem[]>([]);
  const [searching, setSearching] = useState(false);
  const [picking, setPicking] = useState(false);
  const [lastPickFlash, setLastPickFlash] = useState<number | null>(null);

  // Find my participant_id
  const myParticipantId = draft?.participants.find(
    (p) => me && p.display_name === me.display_name,
  )?.participant_id ?? null;

  const isMyTurn = myParticipantId !== null && nextParticipantId === myParticipantId;
  const isAdmin = user?.isAdmin ?? false;

  // Load initial draft state
  useEffect(() => {
    if (!selectedSeason || !draftId) return;
    async function load() {
      setLoading(true);
      try {
        // Try both phases to find the draft
        for (const phase of ["preseason", "winter"]) {
          try {
            const detail = await apiClient.get<DraftDetailResponse>(
              `/drafts/${selectedSeason!.id}/${phase}`,
            );
            // Find matching draft by checking if any draft in this phase matches
            const drafts = await apiClient.get<{ drafts: { id: number; phase: string }[] }>(
              `/drafts/${selectedSeason!.id}`,
            );
            const match = drafts.drafts.find((d) => d.id === draftId);
            if (match && match.phase === phase) {
              setDraft(detail);
              setPicks(detail.picks);
              setNextParticipantId(detail.next_participant_id);
              break;
            }
          } catch {
            // continue
          }
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Error cargando draft");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [selectedSeason, draftId]);

  // WebSocket events
  const handleWsEvent = useCallback(
    (event: { type: string; pick?: DraftPickEntry; next_participant_id?: number }) => {
      if (event.type === "pick_added" && event.pick) {
        setPicks((prev) => [...prev, event.pick!]);
        setNextParticipantId(event.next_participant_id ?? null);
        setLastPickFlash(event.pick.pick_number);
        setTimeout(() => setLastPickFlash(null), 2000);
        // Clear search results when a pick is made
        setSearchResults([]);
        setSearch("");
      }
    },
    [],
  );

  const { online, connected } = useDraftWebSocket(draftId, handleWsEvent);

  // Search players
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
        setSearchResults(res.players.filter((p) => !p.is_already_picked));
      } catch {
        setSearchResults([]);
      } finally {
        setSearching(false);
      }
    }, 300);
    return () => clearTimeout(timeout);
  }, [search, posFilter, draftId]);

  // Make a pick
  async function handlePick(playerId: number) {
    setPicking(true);
    setError(null);
    try {
      await apiClient.post(`/drafts/${draftId}/picks`, {
        player_id: playerId,
      });
      // WebSocket will broadcast the pick to everyone including us
      setSearch("");
      setSearchResults([]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al hacer pick");
    } finally {
      setPicking(false);
    }
  }

  // Current turn participant name
  const currentTurnName = draft?.participants.find(
    (p) => p.participant_id === nextParticipantId,
  )?.display_name ?? "...";

  const currentPickNumber = picks.length + 1;
  const participantCount = draft?.participants.length ?? 1;
  const currentRound = Math.floor(picks.length / participantCount) + 1;

  if (authLoading || loading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-vpv-accent border-t-transparent" />
      </div>
    );
  }

  if (!user) {
    router.push("/login");
    return null;
  }

  if (!draft) {
    return (
      <div className="py-10 text-center text-vpv-text-muted">
        Draft no encontrado.
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-vpv-text">
            Draft {draft.phase === "preseason" ? "Pretemporada" : "Invierno"}
          </h1>
          <p className="text-xs text-vpv-text-muted">
            {draft.draft_type === "snake" ? "Serpiente" : "Lineal"} &middot;{" "}
            Ronda {currentRound} &middot; Pick #{currentPickNumber}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`h-2 w-2 rounded-full ${connected ? "bg-green-500" : "bg-red-500"}`}
          />
          <span className="text-xs text-vpv-text-muted">
            {online} online
          </span>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Turn indicator + pick interface */}
      {isMyTurn ? (
        <div className="rounded-lg border-2 border-vpv-accent bg-vpv-accent/10 p-4">
          <p className="mb-3 text-center text-lg font-bold text-vpv-accent">
            Tu turno!
          </p>
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Buscar jugador..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              autoFocus
              className="flex-1 rounded-lg border border-vpv-border bg-vpv-bg px-3 py-2 text-sm text-vpv-text placeholder:text-vpv-text-muted/50 focus:border-vpv-accent focus:outline-none"
            />
            <select
              value={posFilter}
              onChange={(e) => setPosFilter(e.target.value)}
              className="rounded-lg border border-vpv-border bg-vpv-bg px-2 py-2 text-sm text-vpv-text"
            >
              <option value="">Pos</option>
              {["POR", "DEF", "MED", "DEL"].map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </div>

          {/* Search results */}
          {searching && (
            <p className="mt-2 text-center text-xs text-vpv-text-muted">Buscando...</p>
          )}
          {searchResults.length > 0 && (
            <div className="mt-2 max-h-60 space-y-1 overflow-y-auto">
              {searchResults.map((player) => (
                <button
                  key={player.id}
                  onClick={() => handlePick(player.id)}
                  disabled={picking}
                  className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors hover:bg-vpv-accent/20 disabled:opacity-50"
                >
                  <PlayerAvatar
                    photoPath={player.photo_path}
                    name={player.display_name}
                    size={32}
                  />
                  <span
                    className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${POS_COLORS[player.position] ?? ""}`}
                  >
                    {player.position}
                  </span>
                  <span className="flex-1 font-medium text-vpv-text">
                    {player.display_name}
                  </span>
                  <span className="text-xs text-vpv-text-muted">
                    {player.team_name}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-4 text-center">
          <p className="text-sm text-vpv-text-muted">Turno de</p>
          <p className="text-lg font-bold text-vpv-text">{currentTurnName}</p>
          <p className="text-xs text-vpv-text-muted">
            Pick #{currentPickNumber} &middot; Ronda {currentRound}
          </p>
        </div>
      )}

      {/* Admin override: pick for anyone */}
      {isAdmin && !isMyTurn && (
        <details className="rounded-lg border border-amber-500/30 bg-amber-500/5">
          <summary className="cursor-pointer px-4 py-2 text-xs font-medium text-amber-400">
            Admin: hacer pick por {currentTurnName}
          </summary>
          <div className="px-4 pb-3">
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Buscar jugador..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="flex-1 rounded-lg border border-vpv-border bg-vpv-bg px-3 py-2 text-sm text-vpv-text placeholder:text-vpv-text-muted/50 focus:border-vpv-accent focus:outline-none"
              />
              <select
                value={posFilter}
                onChange={(e) => setPosFilter(e.target.value)}
                className="rounded-lg border border-vpv-border bg-vpv-bg px-2 py-2 text-sm text-vpv-text"
              >
                <option value="">Pos</option>
                {["POR", "DEF", "MED", "DEL"].map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </div>
            {searchResults.length > 0 && (
              <div className="mt-2 max-h-40 space-y-1 overflow-y-auto">
                {searchResults.map((player) => (
                  <button
                    key={player.id}
                    onClick={() => handlePick(player.id)}
                    disabled={picking}
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors hover:bg-vpv-accent/20 disabled:opacity-50"
                  >
                    <PlayerAvatar
                      photoPath={player.photo_path}
                      name={player.display_name}
                      size={28}
                    />
                    <span
                      className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${POS_COLORS[player.position] ?? ""}`}
                    >
                      {player.position}
                    </span>
                    <span className="flex-1 font-medium text-vpv-text">
                      {player.display_name}
                    </span>
                    <span className="text-xs text-vpv-text-muted">
                      {player.team_name}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </details>
      )}

      {/* Recent picks */}
      <div>
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-vpv-text-muted">
          Picks ({picks.length})
        </h2>
        <div className="space-y-1">
          {[...picks].reverse().map((pick) => (
            <div
              key={pick.id}
              className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-all ${
                lastPickFlash === pick.pick_number
                  ? "border border-vpv-accent bg-vpv-accent/10"
                  : "bg-vpv-card"
              }`}
            >
              <span className="w-8 text-center text-xs tabular-nums text-vpv-text-muted">
                #{pick.pick_number}
              </span>
              <span className="w-6 text-center text-[10px] text-vpv-text-muted">
                R{pick.round_number}
              </span>
              <PlayerAvatar
                photoPath={pick.photo_path}
                name={pick.player_name}
                size={28}
              />
              <span
                className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${POS_COLORS[pick.position] ?? ""}`}
              >
                {pick.position}
              </span>
              <span className="flex-1 truncate font-medium text-vpv-text">
                {pick.player_name}
              </span>
              <span className="text-xs text-vpv-text-muted">
                {pick.team_name}
              </span>
              <span className="rounded-full bg-vpv-bg px-2 py-0.5 text-[10px] text-vpv-text-muted">
                {pick.display_name}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Participants */}
      <div>
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-vpv-text-muted">
          Participantes
        </h2>
        <div className="flex flex-wrap gap-2">
          {draft.participants
            .sort((a, b) => (a.draft_order ?? 99) - (b.draft_order ?? 99))
            .map((p) => {
              const pickCount = picks.filter(
                (pk) => pk.participant_id === p.participant_id,
              ).length;
              const isCurrent = p.participant_id === nextParticipantId;
              return (
                <div
                  key={p.participant_id}
                  className={`rounded-lg px-3 py-1.5 text-xs font-medium ${
                    isCurrent
                      ? "border-2 border-vpv-accent bg-vpv-accent/20 text-vpv-accent"
                      : "bg-vpv-card text-vpv-text-muted"
                  }`}
                >
                  {p.display_name}{" "}
                  <span className="opacity-60">({pickCount})</span>
                </div>
              );
            })}
        </div>
      </div>
    </div>
  );
}
