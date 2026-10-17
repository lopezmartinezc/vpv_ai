"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type JSX } from "react";
import { DeadlineBanner } from "@/features/lineup/deadline-banner";
import { MatchCards } from "@/features/lineup/match-cards";
import { PlayerCard } from "@/features/lineup/player-card";
import { PositionTabs } from "@/features/lineup/position-tabs";
import {
  POSITION_LABELS,
  POSITION_ORDER,
  canAddToPosition,
  countsByPosition,
  type Position,
} from "@/features/lineup/positions";
import {
  ProposalCard,
  isLineupProposal,
  type LineupProposal,
} from "@/features/lineup/proposal-card";
import { SeasonLink as Link } from "@/components/ui/season-link";
import { useParams } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import { apiClient, ApiClientError } from "@/lib/api-client";
import { type OpponentStrength } from "@/lib/fixture-difficulty";
import { PitchView } from "@/components/ui/pitch-view";
import type { PitchPlayer } from "@/components/ui/pitch-view";
import { SkeletonTable } from "@/components/ui/skeleton";
import { AssistantPanel, type AskResponse } from "@/components/assistant/assistant-panel";
import { LIGA_PLAYOFF_NAME } from "@/lib/playoff-name";
import {
  LineupAdminBar,
  SuggestionPanel,
  applySuggestion,
  readingsByPlayer,
  coverageByTeam,
  type LineupIntelResponse,
  type SuggestionResponse,
} from "@/components/lineup/lineup-intel";
import type {
  MatchdayDetailResponse,
  MyLineupResponse,
  PlayerPrediction,
  PredictionsResponse,
  SquadPlayerEntry,
  ValidFormation,
} from "@/types";

// ---------------------------------------------------------------------------
// Types & Constants
// ---------------------------------------------------------------------------

interface LineupSubmitBody {
  formation: string;
  players: { player_id: number; position_slot: string }[];
}

const LINEUP_SUGGESTIONS = [
  "Propón mi once y explica los casos dudosos",
  "¿Quién de mi plantilla es duda esta jornada?",
  "¿Qué dicen las webs de mis delanteros?",
  `¿Qué ha alineado mi rival de la ${LIGA_PLAYOFF_NAME}?`,
];

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function AlineacionPage(): JSX.Element {
  const { user } = useAuth();
  const { selectedSeason } = useSeason();
  const { numero } = useParams<{ numero: string }>();
  return <LineupEditor key={`${user?.id}:${selectedSeason?.id}:${numero}`} />;
}

function LineupEditor(): JSX.Element {
  const params = useParams<{ numero: string }>();
  const numero = Number(params.numero);
  const { user, loading: authLoading } = useAuth();
  const { selectedSeason, loading: seasonLoading } = useSeason();

  // API calls
  const { data: myLineup, loading: myLineupLoading, refetch: refetchLineup } =
    useFetch<MyLineupResponse>(
      selectedSeason ? `/lineups/${selectedSeason.id}/${numero}/me` : null,
    );

  const { data: matchdayData, loading: matchdayLoading } =
    useFetch<MatchdayDetailResponse>(
      selectedSeason ? `/matchdays/${selectedSeason.id}/${numero}` : null,
    );

  const { data: formationsData, loading: formationsLoading } = useFetch<
    ValidFormation[]
  >("/seasons/formations");

  // Admin-only: predictions for player cards
  const isAdmin = user?.isAdmin ?? false;
  const { data: predictionsData } = useFetch<PredictionsResponse>(
    isAdmin && selectedSeason
      ? `/stats/${selectedSeason.id}/predictions?matchday=${numero}`
      : null,
  );
  // Admin-only, like the predictions above. Opponent strength for THIS
  // matchday, so each card can say whether the fixture is soft or hard for that
  // player's position. Measured effect is 1.4-2.6 points per slot, which over
  // eleven slots is the biggest weekly lever there is — which is exactly why it
  // is not shown to the participants the admin is competing against.
  const { data: fixturesData } = useFetch<{
    fixtures: {
      matchday: number;
      team_name: string;
      opponent_attack: number;
      opponent_defence: number;
    }[];
  }>(
    isAdmin && selectedSeason
      ? `/stats/${selectedSeason.id}/fixtures?desde=${numero}&jornadas=1`
      : null,
  );
  const fixtureByTeam = useMemo(() => {
    const map = new Map<string, OpponentStrength>();
    for (const f of fixturesData?.fixtures ?? []) {
      if (f.matchday !== numero) continue;
      map.set(f.team_name, {
        opponent_attack: f.opponent_attack,
        opponent_defence: f.opponent_defence,
      });
    }
    return map;
  }, [fixturesData, numero]);

  const predictionsMap = useMemo(() => {
    if (!predictionsData?.predictions) return new Map<number, PlayerPrediction>();
    return new Map(predictionsData.predictions.map((p) => [p.player_id, p]));
  }, [predictionsData]);

  // Admin-only, like the predictions: what futbolfantasy, analiticafantasy and
  // predicted11's best predictors say about each player this matchday.
  const { data: intelData, refetch: refetchIntel } = useFetch<LineupIntelResponse>(
    isAdmin && selectedSeason
      ? `/lineup-intel/${selectedSeason.id}/${numero}`
      : null,
  );
  const readingsMap = useMemo(() => readingsByPlayer(intelData), [intelData]);
  const coverageMap = useMemo(() => coverageByTeam(intelData), [intelData]);

  // ---------------------------------------------------------------------------
  // Local state
  // ---------------------------------------------------------------------------

  const [selectedPlayers, setSelectedPlayers] = useState<SquadPlayerEntry[]>(
    [],
  );
  const [activeTab, setActiveTab] = useState<Position>("POR");
  const [submitting, setSubmitting] = useState(false);
  const [submitResult, setSubmitResult] = useState<{
    ok: boolean;
    message: string;
  } | null>(null);
  const [initialized, setInitialized] = useState(false);
  // The eleven last proposed by the optimizer, to show why each one is there.
  const [suggestion, setSuggestion] = useState<SuggestionResponse | null>(null);
  // The eleven the chat last proposed, and the selection it replaced (to undo).
  const [proposal, setProposal] = useState<LineupProposal | null>(null);
  const [beforeProposal, setBeforeProposal] = useState<SquadPlayerEntry[] | null>(null);
  const prevCountRef = useRef(0);

  // Initialize from existing lineup
  useEffect(() => {
    if (initialized || !myLineup) return;

    if (myLineup.current_lineup) {
      const squadMap = new Map(myLineup.squad.map((s) => [s.player_id, s]));
      const preSelected: SquadPlayerEntry[] = [];
      for (const lp of myLineup.current_lineup.players) {
        const sq = squadMap.get(lp.player_id);
        if (sq) preSelected.push(sq);
      }
      setSelectedPlayers(preSelected);
    }

    setInitialized(true);
  }, [myLineup, initialized]);

  // ---------------------------------------------------------------------------
  // Derived values
  // ---------------------------------------------------------------------------

  const selectedIds = useMemo(
    () => new Set(selectedPlayers.map((p) => p.player_id)),
    [selectedPlayers],
  );

  const currentCounts = useMemo(
    () => countsByPosition(selectedPlayers),
    [selectedPlayers],
  );

  /** Formations still reachable with current selection. */
  const possibleFormations = useMemo(() => {
    if (!formationsData) return [];
    const c = currentCounts;
    return formationsData.filter(
      (f) =>
        c.DEF <= f.defenders &&
        c.MED <= f.midfielders &&
        c.DEL <= f.forwards,
    );
  }, [currentCounts, formationsData]);

  /** Exact formation when 11 players are selected. */
  const detectedFormation = useMemo<ValidFormation | null>(() => {
    if (selectedPlayers.length !== 11 || currentCounts.POR !== 1) return null;
    return (
      formationsData?.find(
        (f) =>
          f.defenders === currentCounts.DEF &&
          f.midfielders === currentCounts.MED &&
          f.forwards === currentCounts.DEL,
      ) ?? null
    );
  }, [selectedPlayers.length, currentCounts, formationsData]);

  /** What the chat is told the user has on screen right now, unsent. */
  const chatDraft = useMemo(
    () => ({
      formation: detectedFormation?.formation ?? null,
      players: selectedPlayers.map((p) => ({
        player_id: p.player_id,
        position_slot: p.position,
      })),
    }),
    [detectedFormation, selectedPlayers],
  );

  /** Formation string for PitchView display. */
  const displayFormation =
    detectedFormation?.formation ??
    possibleFormations[0]?.formation ??
    "1-4-3-3";

  /** Whether each position can accept more players. */
  const canAdd = useMemo<Record<Position, boolean>>(
    () => ({
      POR: canAddToPosition(
        "POR",
        currentCounts,
        formationsData ?? [],
        selectedPlayers.length,
      ),
      DEF: canAddToPosition(
        "DEF",
        currentCounts,
        formationsData ?? [],
        selectedPlayers.length,
      ),
      MED: canAddToPosition(
        "MED",
        currentCounts,
        formationsData ?? [],
        selectedPlayers.length,
      ),
      DEL: canAddToPosition(
        "DEL",
        currentCounts,
        formationsData ?? [],
        selectedPlayers.length,
      ),
    }),
    [currentCounts, formationsData, selectedPlayers.length],
  );

  const lineupComplete = detectedFormation !== null;

  // Group squad players by position
  const playersByPosition = useMemo<Record<Position, SquadPlayerEntry[]>>(
    () => {
      const squad = myLineup?.squad ?? [];
      const sortFn = (a: SquadPlayerEntry, b: SquadPlayerEntry) =>
        a.display_name.localeCompare(b.display_name);
      return {
        POR: squad.filter((p) => p.position === "POR").sort(sortFn),
        DEF: squad.filter((p) => p.position === "DEF").sort(sortFn),
        MED: squad.filter((p) => p.position === "MED").sort(sortFn),
        DEL: squad.filter((p) => p.position === "DEL").sort(sortFn),
      };
    },
    [myLineup],
  );

  // Build PitchView players
  const pitchPlayers = useMemo<PitchPlayer[]>(
    () =>
      selectedPlayers.map((p) => ({
        player_id: p.player_id,
        name: p.display_name,
        photo_path: p.photo_path,
        position_slot: p.position,
      })),
    [selectedPlayers],
  );

  // ---------------------------------------------------------------------------
  // Auto-advance tab when a position fills up (only on player addition)
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!formationsData || selectedPlayers.length <= prevCountRef.current) {
      prevCountRef.current = selectedPlayers.length;
      return;
    }
    prevCountRef.current = selectedPlayers.length;

    const counts = countsByPosition(selectedPlayers);
    if (
      !canAddToPosition(activeTab, counts, formationsData, selectedPlayers.length)
    ) {
      const nextTab = POSITION_ORDER.find((pos) =>
        canAddToPosition(pos, counts, formationsData, selectedPlayers.length),
      );
      if (nextTab) setActiveTab(nextTab);
    }
  }, [selectedPlayers, activeTab, formationsData]);

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  const handleTogglePlayer = useCallback(
    (player: SquadPlayerEntry) => {
      setSubmitResult(null);
      setSelectedPlayers((prev) => {
        const pos = player.position as Position;
        const isAlreadySelected = prev.some(
          (p) => p.player_id === player.player_id,
        );

        if (isAlreadySelected) {
          return prev.filter((p) => p.player_id !== player.player_id);
        }

        const counts = countsByPosition(prev);
        if (!canAddToPosition(pos, counts, formationsData ?? [], prev.length)) {
          return prev;
        }

        return [...prev, player];
      });
    },
    [formationsData],
  );

  const handleRemoveFromPitch = useCallback((playerId: number) => {
    setSubmitResult(null);
    setSelectedPlayers((prev) =>
      prev.filter((p) => p.player_id !== playerId),
    );
  }, []);

  // Fills the pitch with the proposed eleven. Sends nothing: the admin
  // adjusts and submits as with any other lineup.
  const handleSuggestion = useCallback(
    (proposed: SuggestionResponse) => {
      if (!myLineup) return;
      setSubmitResult(null);
      setSelectedPlayers(applySuggestion(myLineup.squad, proposed));
      setSuggestion(proposed);
    },
    [myLineup],
  );

  const handleReply = useCallback((res: AskResponse) => {
    if (!isLineupProposal(res.proposal)) return;
    setProposal(res.proposal);
    setBeforeProposal(null);
  }, []);

  const applyProposal = useCallback(() => {
    if (!myLineup || !proposal) return;
    const byId = new Map(myLineup.squad.map((p) => [p.player_id, p]));
    const next = proposal.players
      .map((p) => byId.get(p.player_id))
      .filter((p): p is SquadPlayerEntry => p !== undefined);
    setBeforeProposal(selectedPlayers);
    setSelectedPlayers(next);
    setSubmitResult(null);
  }, [myLineup, proposal, selectedPlayers]);

  const undoProposal = useCallback(() => {
    if (beforeProposal) setSelectedPlayers(beforeProposal);
    setBeforeProposal(null);
  }, [beforeProposal]);

  const discardProposal = useCallback(() => {
    setProposal(null);
    setBeforeProposal(null);
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!selectedSeason || !detectedFormation || submitting) return;

    setSubmitting(true);
    setSubmitResult(null);

    const body: LineupSubmitBody = {
      formation: detectedFormation.formation,
      players: selectedPlayers.map((p) => ({
        player_id: p.player_id,
        position_slot: p.position,
      })),
    };

    try {
      await apiClient.post(`/lineups/${selectedSeason.id}/${numero}`, body);
      refetchLineup();
      setSubmitResult({
        ok: true,
        message: "Alineacion enviada. Revisa Telegram para la confirmacion.",
      });
    } catch (err) {
      const message =
        err instanceof ApiClientError
          ? err.error.message
          : "Error al enviar la alineacion.";
      setSubmitResult({ ok: false, message });
    } finally {
      setSubmitting(false);
    }
  }, [
    selectedSeason,
    detectedFormation,
    submitting,
    selectedPlayers,
    numero,
    refetchLineup,
  ]);

  // ---------------------------------------------------------------------------
  // Loading / Error states
  // ---------------------------------------------------------------------------

  const isLoading =
    authLoading ||
    seasonLoading ||
    myLineupLoading ||
    matchdayLoading ||
    formationsLoading;

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="h-4 w-48 animate-pulse rounded bg-vpv-border" />
        <div className="h-8 w-64 animate-pulse rounded bg-vpv-border" />
        <div className="mx-auto aspect-[3/4] w-full max-w-sm animate-pulse rounded-xl bg-vpv-border" />
        <SkeletonTable rows={4} />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="py-12 text-center">
        <p className="text-vpv-text-muted">
          Debes{" "}
          <Link href="/login" className="text-vpv-accent underline">
            iniciar sesion
          </Link>{" "}
          para enviar tu alineacion.
        </p>
      </div>
    );
  }

  if (!selectedSeason) {
    return (
      <div className="py-12 text-center text-vpv-text-muted">
        No hay temporada activa.
      </div>
    );
  }

  if (!myLineup || !formationsData) {
    return (
      <div className="py-12 text-center text-vpv-text-muted">
        No se pudo cargar la informacion. Intentalo de nuevo.
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="space-y-5">
      {/* Breadcrumb */}
      <nav
        aria-label="Navegacion"
        className="flex items-center gap-2 text-sm text-vpv-text-muted"
      >
        <Link
          href="/jornadas"
          className="transition-colors hover:text-vpv-text"
        >
          Jornadas
        </Link>
        <span aria-hidden="true">/</span>
        <Link
          href={`/jornadas/${numero}`}
          className="transition-colors hover:text-vpv-text"
        >
          Jornada {numero}
        </Link>
        <span aria-hidden="true">/</span>
        <span className="text-vpv-text">Mi alineacion</span>
      </nav>

      {/* Header row */}
      <div className="flex items-baseline justify-between">
        <h1 className="text-xl font-bold text-vpv-text sm:text-2xl">
          Alineacion — J{numero}
        </h1>
        <span className="text-sm font-medium text-vpv-text-muted">
          {myLineup.display_name}
        </span>
      </div>

      {/* Deadline */}
      <DeadlineBanner
        deadlineAt={matchdayData?.deadline_at ?? null}
      />

      {isAdmin && (
        <LineupAdminBar
          seasonId={selectedSeason.id}
          matchday={numero}
          updatedAt={intelData?.updated_at ?? null}
          onRefreshed={refetchIntel}
          onSuggestion={handleSuggestion}
        />
      )}
      {isAdmin && suggestion && (
        <SuggestionPanel suggestion={suggestion} onClose={() => setSuggestion(null)} />
      )}

      {/* Formation auto-detect + counter */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {detectedFormation ? (
            <span className="rounded-lg border border-vpv-success/30 bg-vpv-success/10 px-3 py-1 text-sm font-bold text-vpv-success">
              {detectedFormation.formation}
            </span>
          ) : possibleFormations.length === 1 ? (
            <span className="rounded-lg border border-vpv-accent/30 bg-vpv-accent/10 px-3 py-1 text-sm font-bold text-vpv-accent">
              {possibleFormations[0].formation}
            </span>
          ) : possibleFormations.length > 1 && selectedPlayers.length > 0 ? (
            <span className="text-xs text-vpv-text-muted">
              {possibleFormations.length} formaciones posibles
            </span>
          ) : selectedPlayers.length > 0 && possibleFormations.length === 0 ? (
            <span className="text-xs text-vpv-danger">
              Combinacion no valida
            </span>
          ) : (
            <span className="text-sm text-vpv-text-muted">
              Selecciona 11 jugadores
            </span>
          )}
        </div>
        <span
          className={`text-sm font-bold tabular-nums ${
            lineupComplete ? "text-vpv-success" : "text-vpv-text"
          }`}
        >
          {selectedPlayers.length}/11
        </span>
      </div>

      {/* Two-column layout */}
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start">
        {/* PitchView + Matches: desktop left, mobile below selection */}
        <div className="order-2 w-full space-y-4 lg:order-1 lg:w-[380px] lg:shrink-0">
          <PitchView
            formation={displayFormation}
            players={pitchPlayers}
            onRemovePlayer={handleRemoveFromPitch}
          />

          {matchdayData && (
            <MatchCards
              matches={matchdayData.matches}
              squad={myLineup.squad}
              selectedIds={selectedIds}
            />
          )}
        </div>

        {/* Player selection: desktop right, mobile first */}
        <div className="order-1 flex-1 space-y-3 lg:order-2">
          <PositionTabs
            activeTab={activeTab}
            onTabChange={setActiveTab}
            counts={currentCounts}
            canAdd={canAdd}
          />

          {/* Active tab label */}
          <h2 className="text-xs font-semibold uppercase tracking-wide text-vpv-text-muted">
            {POSITION_LABELS[activeTab]}
          </h2>

          {/* Player grid for active tab */}
          <div className="grid gap-1.5 sm:grid-cols-2" role="tabpanel">
            {playersByPosition[activeTab].map((player) => {
              const isSelected = selectedIds.has(player.player_id);
              const isDisabled = !isSelected && !canAdd[activeTab];

              return (
                <PlayerCard
                  key={player.player_id}
                  player={player}
                  isSelected={isSelected}
                  isDisabled={isDisabled}
                  onToggle={handleTogglePlayer}
                  showPoints={isAdmin}
                  prediction={predictionsMap.get(player.player_id)}
                  fixture={fixtureByTeam.get(player.team_name)}
                  readings={readingsMap.get(player.player_id)}
                  coverage={coverageMap.get(player.team_name)}
                />
              );
            })}
          </div>
        </div>
      </div>

      {isAdmin && (
        <AssistantPanel
          title="Asistente de alineación"
          endpoint={`/lineup-assistant/${selectedSeason.id}/${numero}/ask/stream`}
          intro="Pregunta por tu once. Consulta tu plantilla, las previsiones y las alineaciones probables de futbolfantasy y analiticafantasy; no opina por su cuenta."
          suggestions={LINEUP_SUGGESTIONS}
          placeholder="Pregunta algo sobre tu alineación…"
          historyLimit={40}
          extraBody={{ draft: chatDraft }}
          onReply={handleReply}
        />
      )}
      {isAdmin && proposal && (
        <ProposalCard
          proposal={proposal}
          applied={beforeProposal !== null}
          onApply={applyProposal}
          onUndo={undoProposal}
          onDiscard={discardProposal}
        />
      )}

      {/* Submit area */}
      <div className="sticky bottom-0 -mx-4 border-t border-vpv-border bg-vpv-bg px-4 py-4 sm:mx-0 sm:static sm:border-0 sm:bg-transparent sm:p-0">
        {submitResult && (
          <div
            role="alert"
            aria-live="assertive"
            className={`mb-3 rounded-lg border px-4 py-3 text-sm ${
              submitResult.ok
                ? "border-vpv-success/40 bg-vpv-success/10 text-vpv-success"
                : "border-vpv-danger/40 bg-vpv-danger/10 text-vpv-danger"
            }`}
          >
            {submitResult.message}
          </div>
        )}

        <button
          type="button"
          onClick={handleSubmit}
          disabled={!lineupComplete || submitting}
          className={`w-full rounded-lg px-6 py-3 text-sm font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-vpv-accent ${
            lineupComplete && !submitting
              ? "bg-vpv-accent text-white hover:bg-vpv-accent-hover"
              : "cursor-not-allowed bg-vpv-border text-vpv-text-muted"
          }`}
        >
          {submitting ? "Enviando..." : "Enviar alineacion"}
        </button>

        {!lineupComplete && selectedPlayers.length > 0 && (
          <p className="mt-2 text-center text-xs text-vpv-text-muted">
            Selecciona exactamente 11 jugadores
          </p>
        )}
      </div>
    </div>
  );
}
