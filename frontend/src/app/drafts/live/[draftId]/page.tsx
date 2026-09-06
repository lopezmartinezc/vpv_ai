"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import { useDraftWebSocket, type DraftWSEvent } from "@/hooks/use-draft-websocket";
import { apiClient } from "@/lib/api-client";
import { PlayerAvatar } from "@/components/ui/player-avatar";
import { WishlistPanel } from "@/components/draft/wishlist-panel";
import { RosterCounter } from "@/components/draft/roster-counter";
import { TIER_COLORS, TIER_LABELS } from "@/lib/draft-scorecard";
import {
  PLAYER_TAG_CLASSES,
  PLAYER_TAG_EMOJI,
  PLAYER_TAG_LABELS,
  PLAYER_TAGS,
} from "@/lib/player-tags";
import type {
  DraftDetailResponse,
  DraftPickEntry,
  DraftPlayerStatsResponse,
  DraftTeamOption,
} from "@/types";

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
  permissions: number;
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
  const searchParams = useSearchParams();
  const testMode = searchParams.get("test") === "true";
  const { user, loading: authLoading } = useAuth();
  const { selectedSeason } = useSeason();
  const { data: me } = useFetch<MeResponse>(user ? "/auth/me" : null);

  const [draft, setDraft] = useState<DraftDetailResponse | null>(null);
  const [picks, setPicks] = useState<DraftPickEntry[]>([]);
  const [nextParticipantId, setNextParticipantId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Bumped on every pick_added/pick_deleted so child panels (wishlist)
  // can refresh derived state without owning their own WS connection.
  const [pickEventCount, setPickEventCount] = useState(0);
  const [autoPickToast, setAutoPickToast] = useState<string | null>(null);

  // Player search
  const [search, setSearch] = useState("");
  const [posFilter, setPosFilter] = useState<string>("");
  const [teamFilter, setTeamFilter] = useState<string>("");
  const [searchResults, setSearchResults] = useState<PlayerSearchItem[]>([]);
  const [searching, setSearching] = useState(false);
  const [picking, setPicking] = useState(false);
  const [lastPickFlash, setLastPickFlash] = useState<number | null>(null);

  // Admin stats (loaded once)
  const [adminStats, setAdminStats] = useState<DraftPlayerStatsResponse | null>(null);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [showScoreHelp, setShowScoreHelp] = useState(false);

  // Find my participant_id. Prefer matching by user_id (added in
  // c1cfd57) — fall back to display_name when the backend/bundle hasn't
  // shipped the new field yet, so a stale deploy doesn't hide the pick
  // UI from regular participants.
  const myUserId = user?.id ? Number(user.id) : null;
  const myParticipantId =
    (myUserId !== null &&
      draft?.participants.find((p) => p.user_id === myUserId)?.participant_id) ||
    (me?.display_name &&
      draft?.participants.find((p) => p.display_name === me.display_name)
        ?.participant_id) ||
    null;

  const isMyTurn = myParticipantId !== null && nextParticipantId === myParticipantId;
  const isAdmin = user?.isAdmin ?? false;
  const hasDraftPerm =
    isAdmin || (((user?.permissions ?? 0) & 0b1000) !== 0); // bit DRAFT = 8

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

  // Load admin stats once
  useEffect(() => {
    if (!isAdmin || !draftId) return;
    apiClient
      .get<DraftPlayerStatsResponse>(`/drafts/${draftId}/players/stats`)
      .then(setAdminStats)
      .catch(() => {});
  }, [isAdmin, draftId]);

  // Fetch the season's teams once for the search filter (id + name).
  const [teamOptions, setTeamOptions] = useState<DraftTeamOption[]>([]);
  useEffect(() => {
    if (!draftId) return;
    apiClient
      .get<DraftTeamOption[]>(`/drafts/${draftId}/teams`)
      .then(setTeamOptions)
      .catch(() => setTeamOptions([]));
  }, [draftId]);

  // WebSocket events
  const handleWsEvent = useCallback(
    (event: DraftWSEvent) => {
      if (event.type === "pick_added" && event.pick) {
        const pick = event.pick;
        const newPick: DraftPickEntry = {
          id: 0,
          pick_number: pick.pick_number,
          round_number: pick.round_number,
          participant_id: pick.participant_id,
          display_name: pick.display_name,
          draft_order: null,
          player_id: pick.player_id,
          player_name: pick.player_name,
          position: pick.position,
          team_name: pick.team_name,
          photo_path: pick.photo_path ?? null,
          dropped_player_name: null,
          origin: pick.origin ?? "manual",
        };
        setPicks((prev) => [...prev, newPick]);
        setNextParticipantId(event.next_participant_id ?? null);
        setLastPickFlash(event.pick.pick_number);
        setTimeout(() => setLastPickFlash(null), 2000);
        setPickEventCount((c) => c + 1);
        // Remove the just-picked player from the visible results instead of
        // clearing everything — the searcher can keep evaluating the rest.
        setSearchResults((prev) =>
          prev.filter((p) => p.id !== pick.player_id),
        );
        if (
          pick.origin === "auto" &&
          myParticipantId !== null &&
          pick.participant_id === myParticipantId
        ) {
          setAutoPickToast(`Tu auto-pick eligió a ${pick.player_name}`);
          setTimeout(() => setAutoPickToast(null), 4000);
        }
      } else if (event.type === "pick_deleted" && event.pick_number) {
        const deletedNumber = event.pick_number;
        setPicks((prev) => prev.filter((p) => p.pick_number !== deletedNumber));
        setNextParticipantId(event.next_participant_id ?? null);
        setPickEventCount((c) => c + 1);
      } else if (event.type === "draft_status_changed" && event.status) {
        setDraft((prev) =>
          prev ? { ...prev, status: event.status as string } : prev,
        );
      }
    },
    [myParticipantId],
  );

  const { online, connected } = useDraftWebSocket(draftId, handleWsEvent);

  // Search players
  useEffect(() => {
    if (!search.trim() && !posFilter && !teamFilter) {
      setSearchResults([]);
      return;
    }
    const timeout = setTimeout(async () => {
      setSearching(true);
      try {
        const params = new URLSearchParams();
        if (search.trim()) params.set("q", search.trim());
        if (posFilter) params.set("position", posFilter);
        if (teamFilter) params.set("team_id", teamFilter);
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
  }, [search, posFilter, teamFilter, draftId]);

  // Make a pick
  async function handlePick(playerId: number) {
    // Always confirm before sending the pick: it triggers an irreversible
    // WS broadcast + Telegram notification. The wording adapts so a
    // participant picking for themselves sees a shorter message, while an
    // admin picking on behalf of someone else sees the target name.
    const player = searchResults.find((p) => p.id === playerId);
    const targetParticipant = draft?.participants.find(
      (p) => p.participant_id === nextParticipantId,
    );
    const playerLabel = player
      ? `${player.display_name} (${player.position}, ${player.team_name})`
      : `jugador #${playerId}`;
    const pickingForSelf =
      myParticipantId !== null && nextParticipantId === myParticipantId;
    const prompt = pickingForSelf
      ? `¿Confirmar pick?\n\n${playerLabel}`
      : `¿Confirmar pick para ${targetParticipant?.display_name ?? "?"}?\n\n${playerLabel}`;
    if (!window.confirm(prompt)) {
      return;
    }
    setPicking(true);
    setError(null);
    try {
      if (testMode) {
        // Test mode: simulate pick locally without hitting the API
        const player = searchResults.find((p) => p.id === playerId);
        const fakePick: DraftPickEntry = {
          id: 0,
          pick_number: picks.length + 1,
          round_number: Math.floor(picks.length / (draft?.participants.length ?? 1)) + 1,
          participant_id: nextParticipantId ?? 0,
          display_name: draft?.participants.find((p) => p.participant_id === nextParticipantId)?.display_name ?? "?",
          draft_order: null,
          player_id: playerId,
          player_name: player?.display_name ?? "?",
          position: player?.position ?? "?",
          team_name: player?.team_name ?? "?",
          photo_path: player?.photo_path ?? null,
          dropped_player_name: null,
        };
        setPicks((prev) => [...prev, fakePick]);
        // Advance turn (simplified — doesn't handle snake perfectly)
        const participants = draft?.participants.sort((a, b) => (a.draft_order ?? 99) - (b.draft_order ?? 99)) ?? [];
        const currentIdx = participants.findIndex((p) => p.participant_id === nextParticipantId);
        const nextIdx = (currentIdx + 1) % participants.length;
        setNextParticipantId(participants[nextIdx]?.participant_id ?? null);
        setLastPickFlash(fakePick.pick_number);
        setTimeout(() => setLastPickFlash(null), 2000);
      } else {
        await apiClient.post(`/drafts/${draftId}/picks`, {
          player_id: playerId,
        });
        // WebSocket will broadcast the pick to everyone including us
      }
      setSearch("");
      setSearchResults([]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al hacer pick");
    } finally {
      setPicking(false);
    }
  }

  // Delete a pick. Backend validates the rules:
  //   - admin / DRAFT perm: any pick.
  //   - regular user: only their own LAST pick.
  // The UI hides the button when the rules clearly don't allow it.
  async function handleDeletePick(pick: DraftPickEntry) {
    if (!draftId) return;
    if (
      !window.confirm(
        `¿Eliminar el pick #${pick.pick_number} (${pick.player_name})?`,
      )
    ) {
      return;
    }
    try {
      await apiClient.delete(`/drafts/${draftId}/picks/${pick.pick_number}`);
      // WebSocket will broadcast pick_deleted and we'll sync state there.
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al eliminar el pick");
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

  // Helper to find player name from picks or search results
  function findPlayerName(playerId: number): string {
    const fromPick = picks.find((p) => p.player_id === playerId);
    if (fromPick) return fromPick.player_name;
    const fromSearch = searchResults.find((p) => p.id === playerId);
    if (fromSearch) return fromSearch.display_name;
    return `#${playerId}`;
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

      {testMode && (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-2 text-center text-sm font-medium text-amber-400">
          MODO TEST — Los picks no se guardan en la base de datos
        </div>
      )}

      {draft?.status === "paused" && (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm font-medium text-amber-400">
          Draft pausado por el administrador — los picks están bloqueados.
        </div>
      )}

      {draft?.status === "completed" && (
        <div className="rounded-lg border border-green-500/40 bg-green-500/10 px-4 py-3 text-sm font-medium text-green-400">
          Draft finalizado.
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {autoPickToast && (
        <div className="rounded-lg border border-vpv-accent/40 bg-vpv-accent/10 px-4 py-2 text-sm text-vpv-accent">
          {autoPickToast}
        </div>
      )}

      {/* Admin score help / legend */}
      {isAdmin && adminStats && (
        <div>
          <button
            onClick={() => setShowScoreHelp(!showScoreHelp)}
            className={`w-full rounded-lg border px-4 py-2 text-left text-xs font-medium transition-colors ${
              showScoreHelp
                ? "border-sky-500 bg-sky-500/10 text-sky-300"
                : "border-vpv-border bg-vpv-card text-vpv-text-muted hover:text-vpv-text"
            }`}
          >
            {showScoreHelp ? "Ocultar leyenda" : "¿Cómo leo los scores? (Admin)"}
          </button>
          {showScoreHelp && (
            <div className="mt-2 space-y-3 rounded-lg border border-sky-500/30 bg-sky-500/5 p-3 text-[11px] text-vpv-text">
              <div className="rounded border border-sky-500/40 bg-sky-500/10 p-2">
                <p className="mb-1 font-bold text-sky-300">Orden de decisión (decision-tree)</p>
                <ol className="ml-4 list-decimal text-vpv-text-muted">
                  <li>
                    <span className="text-vpv-text">Disponibilidad</span> — si
                    📌 suplente: pásalo. El Paso 0 manda sobre todo lo demás.
                  </li>
                  <li>
                    <span className="text-vpv-text">Tier propio</span> — POR es
                    {" "}<em>evalúa equipo</em> (no avg); el resto van por umbrales de avg_pts.
                  </li>
                  <li>
                    <span className="text-vpv-text">Entorno / equipo</span> —
                    POR y DEF se llevan los puntos pasivos del equipo (clean
                    sheets, gol +8 para DEF). Si 🔄 mover: re-evalúa.
                  </li>
                  <li>
                    <span className="text-vpv-text">Desempate posicional</span>{" "}
                    — DEL: ¿lanza penaltis? · MED: titularidad fija ·
                    DEF: amenaza ofensiva.
                  </li>
                </ol>
              </div>

              <div>
                <p className="mb-1 font-bold text-sky-300">Prioridad (Prio) — el número maestro</p>
                <p className="text-vpv-text-muted">
                  Es el mismo orden que el tablero de <span className="text-vpv-text">Estadísticas → Draft</span>:
                  puntos proyectados el resto de temporada, ajustados por riesgo
                  (pico de forma, banquillo, fiabilidad) <span className="text-vpv-text">y tus tags</span>.
                  El tooltip de cada jugador muestra además:
                </p>
                <ul className="mt-1 ml-3 list-disc text-vpv-text-muted">
                  <li><span className="text-vpv-text">modelo</span> — la Prioridad sin tus tags (Base), para comparar.</li>
                  <li><span className="text-vpv-text">VORP</span> — valor sobre el reemplazo de su posición (escasez).</li>
                  <li><span className="text-vpv-text">Fiab</span> — % de puntos por eventos concretos vs nota (más = repetible).</li>
                  <li><span className="text-vpv-text">DefEq</span> (porteros) — goles que encaja su equipo/partido; menos = mejor.</li>
                </ul>
              </div>

              <div>
                <p className="mb-1 font-bold text-sky-300">Tier por posición</p>
                <p className="mb-1 text-vpv-text-muted">
                  Umbrales de <em>avg_pts</em> distintos por posición — un MED con 6.0
                  no es lo mismo que un DEL con 6.0.
                </p>
                <div className="grid grid-cols-2 gap-1 sm:grid-cols-4">
                  {(["POR", "DEF", "MED", "DEL"] as const).map((pos) => (
                    <div key={pos} className="rounded border border-vpv-card-border bg-vpv-card p-1.5">
                      <p className={`mb-0.5 text-center text-[9px] font-bold ${POS_COLORS[pos]?.split(" ")[1] ?? ""}`}>{pos}</p>
                      <p className="text-[10px] text-vpv-text-muted">
                        {pos === "POR" && "evalúa equipo (rango p25=5.4 a p90=7.6 — tiers no separan)"}
                        {pos === "DEF" && "elite ≥6.6 · sólido ≥5.8 · normal ≥4.9"}
                        {pos === "MED" && "elite ≥6.1 · sólido ≥5.3 · normal ≥4.4"}
                        {pos === "DEL" && "elite ≥7.2 · sólido ≥5.4 · normal ≥4.2"}
                      </p>
                    </div>
                  ))}
                </div>
                <div className="mt-2 flex flex-wrap gap-1">
                  {(["elite", "solid", "normal", "weak", "team_dependent"] as const).map((t) => (
                    <span
                      key={t}
                      className={`rounded px-1.5 py-px text-[9px] font-bold tracking-wide ${TIER_COLORS[t]}`}
                    >
                      {TIER_LABELS[t]}
                    </span>
                  ))}
                </div>
              </div>

              <div>
                <p className="mb-1 font-bold text-sky-300">Tus tags (ajustan la Prioridad)</p>
                <div className="flex flex-wrap gap-1.5">
                  {PLAYER_TAGS.map((t) => (
                    <span key={t.key} className={`rounded px-1.5 py-px text-[9px] font-bold ${t.cls}`}>
                      {t.label}
                    </span>
                  ))}
                </div>
                <p className="mt-1 text-vpv-text-muted">
                  Se ponen en el tablero de Draft (fila expandida). Titular anula el
                  descuento de banquillo; Objetivo/Gol/Penaltis suben, Suplente/Lesión/Evitar bajan.
                </p>
              </div>

              <div>
                <p className="mb-1 font-bold text-sky-300">Banderas de aviso</p>
                <ul className="ml-3 list-none space-y-1 text-vpv-text-muted">
                  <li>
                    <span title="Banquillo">📌</span>{" "}
                    <span className="text-vpv-text">Riesgo de banquillo</span> —
                    rota o juega pocos partidos. La disponibilidad pesa más que
                    el talento: si no juega, no puntúa. (El tag <em>Titular</em> lo anula.)
                  </li>
                  <li>
                    <span title="Nuevo">🆕</span>{" "}
                    <span className="text-vpv-text">Nuevo</span> — sin histórico en
                    La Liga (ascendido/fichaje); proyección con más incertidumbre.
                  </li>
                  <li>
                    <span title="Cambió de equipo">🔄</span>{" "}
                    <span className="text-vpv-text">Cambió de equipo</span> —
                    re-evalúa el entorno (entorno pasivo POR/DEF, penaltis, rol).
                  </li>
                  <li>
                    <span title="Pico de forma">🔻</span>{" "}
                    <span className="text-vpv-text">Pico de forma</span> — su última
                    temporada fue muy por encima de su media. Riesgo de regresión.
                  </li>
                  <li>
                    <span title="Penaltis">⚽</span>{" "}
                    <span className="text-vpv-text">Lanzador de penaltis</span> — la
                    temporada pasada. <strong>OJO:</strong> el rol solo persiste
                    ~44% — verifica quién lanza ESTA temporada.
                  </li>
                </ul>
              </div>

              <div className="border-t border-sky-500/20 pt-2 text-[10px] text-vpv-text-muted">
                Las sugerencias del panel siguiente están ordenadas por
                <span className="text-vpv-text"> Prioridad</span> (el orden maestro del
                tablero). Para el detalle completo, la pestaña{" "}
                <span className="text-vpv-text">Estadísticas → Guía</span>.
              </div>
            </div>
          )}
        </div>
      )}

      {/* Admin suggestions panel */}
      {isAdmin && adminStats && (isMyTurn || true) && (
        <div>
          <button
            onClick={() => setShowSuggestions(!showSuggestions)}
            className={`w-full rounded-lg border px-4 py-2 text-left text-xs font-medium transition-colors ${
              showSuggestions
                ? "border-amber-500 bg-amber-500/10 text-amber-400"
                : "border-vpv-border bg-vpv-card text-vpv-text-muted hover:text-vpv-text"
            }`}
          >
            {showSuggestions ? "Ocultar sugerencias" : "Sugerencias de pick (Admin)"}
          </button>
          {showSuggestions && (
            <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
              {(["POR", "DEF", "MED", "DEL"] as const).map((pos) => {
                const ids = adminStats.suggestions[pos] ?? [];
                return (
                  <div key={pos} className="rounded-lg border border-vpv-card-border bg-vpv-card p-2">
                    <p className={`mb-1 text-center text-[10px] font-bold ${POS_COLORS[pos]?.split(" ")[1] ?? ""}`}>{pos}</p>
                    {ids.map((pid) => {
                      const s = adminStats.players[String(pid)];
                      if (!s) return null;
                      return (
                        <button
                          key={pid}
                          onClick={() => handlePick(pid)}
                          disabled={picking}
                          className="flex w-full items-center justify-between rounded px-1 py-1 text-[10px] transition-colors hover:bg-vpv-accent/10 disabled:opacity-50"
                          title={`Prioridad ${s.priority?.toFixed(0) ?? "—"}${s.priority_base != null ? ` (modelo ${s.priority_base.toFixed(0)})` : ""}${s.vorp != null ? ` · VORP ${s.vorp.toFixed(1)}` : ""}${s.event_share != null ? ` · Fiab ${(s.event_share * 100).toFixed(0)}%` : ""}${pos === "POR" && s.team_goals_conceded != null ? ` · DefEq ${s.team_goals_conceded.toFixed(1)}` : ""}`}
                        >
                          <span className="flex items-center gap-1 truncate text-vpv-text">
                            <span className="truncate">{findPlayerName(pid)}</span>
                            {s.tags?.map((t) => (
                              <span key={t} title={PLAYER_TAG_LABELS[t] ?? t}>
                                {PLAYER_TAG_EMOJI[t] ?? "🏷️"}
                              </span>
                            ))}
                            {s.is_bench_risk && !s.tags?.includes("titular") && <span title="Riesgo de banquillo">📌</span>}
                            {s.is_new && <span title="Sin histórico">🆕</span>}
                            {s.is_peak_year && <span title="Pico de forma (riesgo regresión)">🔻</span>}
                          </span>
                          <span className="ml-1 tabular-nums font-bold text-vpv-accent">{s.priority != null ? s.priority.toFixed(0) : "—"}</span>
                        </button>
                      );
                    })}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Roster composition vs target (for actual participants) */}
      {myParticipantId !== null && (
        <RosterCounter
          positions={picks
            .filter((p) => p.participant_id === myParticipantId)
            .map((p) => p.position)}
        />
      )}

      {/* Auto-pick wishlist (only for actual participants on an active draft) */}
      {myParticipantId !== null && !testMode && draft?.status !== "completed" && (
        <details className="rounded-lg border border-vpv-card-border bg-vpv-card">
          <summary className="cursor-pointer px-4 py-2 text-sm font-medium text-vpv-text">
            Mi auto-pick
          </summary>
          <div className="border-t border-vpv-card-border px-4 py-3">
            <WishlistPanel draftId={draftId} refreshKey={pickEventCount} />
          </div>
        </details>
      )}

      {/* Turn indicator + pick interface */}
      {isMyTurn ? (
        <div className="rounded-lg border-2 border-vpv-accent bg-vpv-accent/10 p-4">
          <p className="mb-3 text-center text-lg font-bold text-vpv-accent">
            Tu turno!
          </p>
          <SearchFilters
            search={search}
            setSearch={setSearch}
            posFilter={posFilter}
            setPosFilter={setPosFilter}
            teamFilter={teamFilter}
            setTeamFilter={setTeamFilter}
            teams={teamOptions}
            autoFocus
          />
          <SearchResults
            results={searchResults}
            searching={searching}
            picking={picking}
            onPick={handlePick}
            adminStats={isAdmin ? adminStats : null}
            suggestions={isAdmin ? adminStats?.suggestions ?? null : null}
          />
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
            <SearchFilters
              search={search}
              setSearch={setSearch}
              posFilter={posFilter}
              setPosFilter={setPosFilter}
              teamFilter={teamFilter}
              setTeamFilter={setTeamFilter}
              teams={teamOptions}
            />
            <SearchResults
              results={searchResults}
              searching={searching}
              picking={picking}
              onPick={handlePick}
              adminStats={adminStats}
              suggestions={adminStats?.suggestions ?? null}
              compact
            />
          </div>
        </details>
      )}

      {/* Recent picks */}
      <div>
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-vpv-text-muted">
          Picks ({picks.length})
        </h2>
        <div className="space-y-1">
          {(() => {
            const lastPickNumber = picks.length
              ? Math.max(...picks.map((p) => p.pick_number))
              : 0;
            return [...picks].reverse().map((pick) => {
              const canDelete =
                hasDraftPerm ||
                (myParticipantId !== null &&
                  pick.participant_id === myParticipantId &&
                  pick.pick_number === lastPickNumber);
              return (
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
              {canDelete && (
                <button
                  type="button"
                  onClick={() => handleDeletePick(pick)}
                  aria-label={`Eliminar pick #${pick.pick_number}`}
                  title={
                    hasDraftPerm
                      ? "Eliminar pick (admin)"
                      : "Deshacer mi último pick"
                  }
                  className="ml-1 inline-flex h-6 w-6 items-center justify-center rounded text-vpv-text-muted transition-colors hover:bg-red-500/15 hover:text-red-500"
                >
                  ✕
                </button>
              )}
            </div>
              );
            });
          })()}
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

// Tier colours from docs/DRAFT_SCORECARD.md. Each colour matches the
// position colour family but with a clear hierarchy: elite > solid >
// normal > weak. The admin sees these as a quick "should I pick this
// player at all" signal.
// Tier / signal colors are shared with the Draft Retro analytics page —
// keep them in src/lib/draft-scorecard.ts so any tweak hits both surfaces.

function SearchFilters({
  search,
  setSearch,
  posFilter,
  setPosFilter,
  teamFilter,
  setTeamFilter,
  teams,
  autoFocus,
}: {
  search: string;
  setSearch: (v: string) => void;
  posFilter: string;
  setPosFilter: (v: string) => void;
  teamFilter: string;
  setTeamFilter: (v: string) => void;
  teams: DraftTeamOption[];
  autoFocus?: boolean;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      <input
        type="text"
        placeholder="Buscar jugador..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        autoFocus={autoFocus}
        className="min-w-0 flex-1 rounded-lg border border-vpv-border bg-vpv-bg px-3 py-2 text-sm text-vpv-text placeholder:text-vpv-text-muted/50 focus:border-vpv-accent focus:outline-none"
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
      {teams.length > 0 && (
        <select
          value={teamFilter}
          onChange={(e) => setTeamFilter(e.target.value)}
          className="rounded-lg border border-vpv-border bg-vpv-bg px-2 py-2 text-sm text-vpv-text"
        >
          <option value="">Equipo</option>
          {teams.map((t) => (
            <option key={t.id} value={String(t.id)}>{t.name}</option>
          ))}
        </select>
      )}
    </div>
  );
}

function SearchResults({
  results,
  searching,
  picking,
  onPick,
  adminStats,
  suggestions,
  compact,
}: {
  results: PlayerSearchItem[];
  searching: boolean;
  picking: boolean;
  onPick: (id: number) => void;
  adminStats: DraftPlayerStatsResponse | null;
  suggestions: Record<string, number[]> | null;
  compact?: boolean;
}) {
  const suggestedIds = new Set(
    suggestions ? Object.values(suggestions).flat() : [],
  );

  if (searching) {
    return <p className="mt-2 text-center text-xs text-vpv-text-muted">Buscando...</p>;
  }

  if (results.length === 0) return null;

  return (
    <div className={`mt-2 space-y-1 overflow-y-auto ${compact ? "max-h-40" : "max-h-60"}`}>
      {results.map((player) => {
        const stats = adminStats?.players[String(player.id)];
        const isTop = suggestedIds.has(player.id);
        return (
          <button
            key={player.id}
            onClick={() => onPick(player.id)}
            disabled={picking}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors hover:bg-vpv-accent/20 disabled:opacity-50"
          >
            <PlayerAvatar
              photoPath={player.photo_path}
              name={player.display_name}
              size={compact ? 28 : 32}
            />
            <span
              className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${POS_COLORS[player.position] ?? ""}`}
            >
              {player.position}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1">
                <span className="truncate font-medium text-vpv-text">
                  {player.display_name}
                </span>
                {isTop && (
                  <span className="rounded bg-amber-500/20 px-1 py-0.5 text-[9px] font-bold text-amber-400">
                    TOP
                  </span>
                )}
              </div>
              {stats && (
                <div className="mt-0.5 flex flex-wrap items-center gap-1 text-[10px] text-vpv-text-muted">
                  {stats.position_tier && (
                    <span
                      className={`rounded px-1.5 py-px text-[9px] font-bold tracking-wide ${TIER_COLORS[stats.position_tier] ?? ""}`}
                      title={`Tier ${stats.position_tier} en su posici\u00f3n`}
                    >
                      {TIER_LABELS[stats.position_tier] ?? stats.position_tier}
                    </span>
                  )}
                  {/* Admin tags (titular/gol/penaltis/\u2026) */}
                  {stats.tags?.map((t) => (
                    <span
                      key={t}
                      className={`rounded px-1 py-px text-[9px] ${PLAYER_TAG_CLASSES[t] ?? ""}`}
                      title="Tag admin (ajusta la Prioridad)"
                    >
                      {PLAYER_TAG_LABELS[t] ?? t}
                    </span>
                  ))}
                  {stats.is_bench_risk && !stats.tags?.includes("titular") && (
                    <span title="Riesgo de banquillo: rota o juega pocos partidos" className="rounded bg-yellow-500/20 px-1 py-px text-[9px] font-bold text-yellow-300">\ud83d\udccc</span>
                  )}
                  {stats.is_new && (
                    <span title="Sin hist\u00f3rico en La Liga" className="rounded bg-amber-500/15 px-1 py-px text-[9px] text-amber-400">\ud83c\udd95</span>
                  )}
                  {stats.team_changed && (
                    <span title="Cambi\u00f3 de equipo" className="rounded bg-blue-500/15 px-1 py-px text-[9px] text-blue-300">\ud83d\udd04</span>
                  )}
                  {stats.is_peak_year && (
                    <span title="Pico de forma: temporada muy por encima de su media (riesgo de regresi\u00f3n)" className="rounded bg-orange-500/15 px-1 py-px text-[9px] text-orange-300">\ud83d\udd3b</span>
                  )}
                  {stats.is_penalty_taker && (
                    <span title="Lanz\u00f3 penaltis la temporada pasada (verifica el lanzador actual)" className="rounded bg-emerald-500/15 px-1 py-px text-[9px] text-emerald-300">\u26bd</span>
                  )}
                  {/* Priority \u2014 the master number */}
                  <span
                    className="ml-auto font-bold text-vpv-accent tabular-nums"
                    title={`Prioridad ${stats.priority?.toFixed(0) ?? "\u2014"}${stats.priority_base != null ? ` (modelo ${stats.priority_base.toFixed(0)})` : ""}${stats.vorp != null ? ` \u00b7 VORP ${stats.vorp.toFixed(1)}` : ""}${stats.event_share != null ? ` \u00b7 Fiab ${(stats.event_share * 100).toFixed(0)}%` : ""}${player.position === "POR" && stats.team_goals_conceded != null ? ` \u00b7 DefEq ${stats.team_goals_conceded.toFixed(1)}` : ""}`}
                  >
                    Prio {stats.priority != null ? stats.priority.toFixed(0) : "\u2014"}
                  </span>
                  {/* Supporting numbers (small, on the next visual row) */}
                  <span>\u00b7</span>
                  <span>{stats.avg_pts} pts/j</span>
                  <span>PJ:{stats.matchdays_played}</span>
                  <span>T:{stats.starter_pct.toFixed(0)}%</span>
                </div>
              )}
            </div>
            <span className="text-xs text-vpv-text-muted">
              {player.team_name}
            </span>
          </button>
        );
      })}
    </div>
  );
}
