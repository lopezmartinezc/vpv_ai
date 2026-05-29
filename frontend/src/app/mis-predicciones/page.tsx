"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useSeason } from "@/contexts/season-context";
import { useAuth } from "@/contexts/auth-context";
import { useFetch } from "@/hooks/use-fetch";
import { apiClient } from "@/lib/api-client";
import { SkeletonCards } from "@/components/ui/skeleton";
import { TournamentHero } from "@/components/tournament/tournament-hero";
import { CountryFlag } from "@/components/ui/country-flag";
import { PlayerAvatar } from "@/components/ui/player-avatar";
import { SortableTeamCard } from "@/components/tournament/sortable-team-card";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  MouseSensor,
  TouchSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type {
  BracketPredictions,
  BracketResponse,
  PredictionsListResponse,
  PredictionRequest,
  TournamentPrediction,
} from "@/types";

interface TeamOption {
  id: number;
  name: string;
  short_name: string | null;
  logo_path: string | null;
  tournament_group: string | null;
}

interface PlayerOption {
  id: number;
  name: string;
  team_name: string;
  team_id: number;
  position: string | null;
  photo_path: string | null;
}

type Step = "generales" | "grupos" | "eliminatoria";

const STEPS: { key: Step; label: string }[] = [
  { key: "generales", label: "1. Generales" },
  { key: "grupos", label: "2. Grupos" },
  { key: "eliminatoria", label: "3. Eliminatoria" },
];

export default function PrediccionesPage() {
  const { isTournamentContext, loading: seasonLoading } = useSeason();

  if (!seasonLoading && !isTournamentContext) {
    return (
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-8 text-center">
        <p className="text-vpv-text-muted">
          Las predicciones solo aplican a torneos.
        </p>
      </div>
    );
  }

  return <PrediccionesContent />;
}

function PrediccionesContent() {
  const { selectedSeason } = useSeason();
  const { user } = useAuth();
  const isAdmin = user?.isAdmin === true;
  const seasonId = selectedSeason?.id ?? null;

  const { data: teams } = useFetch<TeamOption[]>(
    seasonId ? `/tournaments/${seasonId}/teams` : null,
  );
  const { data: players } = useFetch<PlayerOption[]>(
    seasonId ? `/tournaments/${seasonId}/players` : null,
  );
  const { data: myPred, refetch: refetchMine } = useFetch<TournamentPrediction | null>(
    seasonId ? `/tournaments/${seasonId}/predictions/me` : null,
  );
  const {
    data: allPreds,
    loading: allPredsLoading,
    error: allPredsError,
    refetch: refetchAll,
  } = useFetch<PredictionsListResponse>(
    seasonId ? `/tournaments/${seasonId}/predictions` : null,
  );
  const { data: bracket } = useFetch<BracketResponse>(
    seasonId ? `/tournaments/${seasonId}/bracket` : null,
  );
  const { data: status } = useFetch<{
    season_id: number;
    locked: boolean;
    deadline_at: string | null;
    first_match_at: string | null;
  }>(seasonId ? `/tournaments/${seasonId}/predictions/status` : null);
  const locked = status?.locked === true;

  const [step, setStep] = useState<Step>("generales");
  const [form, setForm] = useState<PredictionRequest>({
    winner_team_id: null,
    top_scorer_player_id: null,
    best_player_id: null,
    dark_horse_team_id: null,
    notes: null,
    bracket_predictions: {},
  });
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (myPred) {
      setForm({
        winner_team_id: myPred.winner_team_id,
        top_scorer_player_id: myPred.top_scorer_player_id,
        best_player_id: myPred.best_player_id,
        dark_horse_team_id: myPred.dark_horse_team_id,
        notes: myPred.notes,
        bracket_predictions: myPred.bracket_predictions ?? {},
      });
    }
  }, [myPred]);

  // Pre-fill group orderings with their default order (as teams are loaded)
  // so that the Eliminatoria step can resolve "1A", "2B" placeholders even
  // before the user touches anything. Existing user picks are preserved.
  useEffect(() => {
    if (!teams || teams.length === 0) return;
    const groupsByLetter: Record<string, TeamOption[]> = {};
    for (const t of teams) {
      if (t.tournament_group) (groupsByLetter[t.tournament_group] ??= []).push(t);
    }
    setForm((f) => {
      const currentGroups = (f.bracket_predictions?.groups ?? {}) as Record<
        string,
        (number | null)[]
      >;
      const newGroups: Record<string, (number | null)[]> = { ...currentGroups };
      let changed = false;
      for (const [letter, teamsInGroup] of Object.entries(groupsByLetter)) {
        const existing = currentGroups[letter] ?? [];
        const seen = new Set<number>();
        const merged: number[] = [];
        for (const id of existing) {
          if (id != null && teamsInGroup.some((t) => t.id === id) && !seen.has(id)) {
            seen.add(id);
            merged.push(id);
          }
        }
        for (const t of teamsInGroup) {
          if (!seen.has(t.id)) {
            seen.add(t.id);
            merged.push(t.id);
          }
        }
        const filled = merged.slice(0, 4);
        if (
          existing.length !== filled.length ||
          existing.some((id, i) => id !== filled[i])
        ) {
          newGroups[letter] = filled;
          changed = true;
        }
      }
      if (!changed) return f;
      return {
        ...f,
        bracket_predictions: { ...f.bracket_predictions, groups: newGroups },
      };
    });
  }, [teams, myPred]);

  async function handleSave() {
    if (!seasonId) return;
    setSaving(true);
    setMessage(null);
    try {
      await apiClient.put(`/tournaments/${seasonId}/predictions/me`, form);
      setMessage("Prediccion guardada");
      await Promise.all([refetchMine(), refetchAll()]);
      setTimeout(() => setMessage(null), 3000);
    } catch {
      setMessage("Error al guardar");
    } finally {
      setSaving(false);
    }
  }

  // ---- Helpers ----
  const teamsById = useMemo(() => {
    const m: Record<number, TeamOption> = {};
    for (const t of teams ?? []) m[t.id] = t;
    return m;
  }, [teams]);

  const teamsByGroup = useMemo(() => {
    const m: Record<string, TeamOption[]> = {};
    for (const t of teams ?? []) {
      if (!t.tournament_group) continue;
      (m[t.tournament_group] ??= []).push(t);
    }
    return m;
  }, [teams]);

  function updateBracket(patch: Partial<BracketPredictions>) {
    setForm((prev) => ({
      ...prev,
      bracket_predictions: { ...(prev.bracket_predictions ?? {}), ...patch },
    }));
  }

  return (
    <div className="space-y-6">
      <TournamentHero
        title="Mis Predicciones"
        subtitle="Acierta los grupos, eliminatorias y premios"
      />

      <div className="flex justify-end">
        <a
          href="/predicciones"
          className="text-xs text-vpv-text-muted hover:text-vpv-text"
        >
          ← Ver predicciones de todos
        </a>
      </div>

      {/* Step tabs */}
      <div className="flex items-center gap-1 border-b border-vpv-border">
        {STEPS.map((s) => (
          <button
            key={s.key}
            type="button"
            onClick={() => setStep(s.key)}
            className={`-mb-px border-b-2 px-3 py-2 text-xs font-medium transition-colors ${
              step === s.key
                ? "border-vpv-accent text-vpv-accent"
                : "border-transparent text-vpv-text-muted hover:text-vpv-text"
            }`}
          >
            {s.label}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2">
          {message && <span className="text-xs text-vpv-text-muted">{message}</span>}
          {!locked && (
            <button
              onClick={handleSave}
              disabled={saving}
              className="rounded bg-vpv-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-vpv-accent/80 disabled:opacity-50"
            >
              {saving ? "Guardando..." : "Guardar"}
            </button>
          )}
        </div>
      </div>

      {locked && (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-300">
          <strong>Predicciones cerradas.</strong> El torneo ya empezó
          {status?.deadline_at
            ? ` (deadline: ${new Date(status.deadline_at).toLocaleString("es-ES")})`
            : ""}
          {" "}— las predicciones se muestran en modo solo lectura.
        </div>
      )}

      {step === "generales" && (
        <fieldset disabled={locked} className="contents">
          <StepGenerales form={form} setForm={setForm} teams={teams ?? []} players={players ?? []} />
        </fieldset>
      )}
      {step === "grupos" && (
        <fieldset disabled={locked} className="contents">
          <StepGrupos
            form={form}
            updateBracket={updateBracket}
            teamsByGroup={teamsByGroup}
            disabled={locked}
          />
        </fieldset>
      )}
      {step === "eliminatoria" && (
        <fieldset disabled={locked} className="contents">
          <StepEliminatoria
            form={form}
            updateBracket={updateBracket}
            teamsById={teamsById}
            teamsByGroup={teamsByGroup}
            bracket={bracket}
            disabled={locked}
          />
        </fieldset>
      )}

      {/* Resumen ranking de predicciones */}
      <AllPredictionsTable
        data={allPreds}
        loading={allPredsLoading}
        error={allPredsError}
        isAdmin={isAdmin}
        seasonId={seasonId}
        onRecalculated={refetchAll}
      />
    </div>
  );
}

// =============================================================================
// Step 1: Generales (champion, top scorer, MVP, dark horse, notes)
// =============================================================================

function StepGenerales({
  form,
  setForm,
  teams,
  players,
}: {
  form: PredictionRequest;
  setForm: React.Dispatch<React.SetStateAction<PredictionRequest>>;
  teams: TeamOption[];
  players: PlayerOption[];
}) {
  const teamsById = useMemo(() => {
    const m: Record<number, TeamOption> = {};
    for (const t of teams) m[t.id] = t;
    return m;
  }, [teams]);
  // playersById removed — PlayerCombobox iterates the list directly and
  // exposes the selected entry via its own internal lookup.

  const winnerTeam = form.winner_team_id ? teamsById[form.winner_team_id] : null;
  const darkHorseTeam = form.dark_horse_team_id ? teamsById[form.dark_horse_team_id] : null;
  // The two player fields render their team flag/photo inline via PlayerCombobox,
  // so we no longer need to derive topScorerTeam / bestPlayerTeam here.

  return (
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
      <div className="border-b border-vpv-border px-4 py-3">
        <h2 className="font-semibold text-vpv-text">Predicciones generales</h2>
        <p className="text-xs text-vpv-text-muted">
          Acierta el campeon, maximo goleador, mejor jugador y la sorpresa.
        </p>
      </div>
      <div className="space-y-3 px-4 py-3">
        <FormSelect
          label="Campeon del torneo"
          value={form.winner_team_id}
          options={teams.map((t) => ({ id: t.id, label: t.name }))}
          onChange={(v) => setForm((f) => ({ ...f, winner_team_id: v }))}
          preview={
            winnerTeam ? (
              <CountryFlag teamName={winnerTeam.name} fallbackLogo={winnerTeam.logo_path} size={22} />
            ) : null
          }
        />
        <FormSelect
          label="Sorpresa del torneo"
          value={form.dark_horse_team_id}
          options={teams.map((t) => ({ id: t.id, label: t.name }))}
          onChange={(v) => setForm((f) => ({ ...f, dark_horse_team_id: v }))}
          preview={
            darkHorseTeam ? (
              <CountryFlag teamName={darkHorseTeam.name} fallbackLogo={darkHorseTeam.logo_path} size={22} />
            ) : null
          }
        />
        <PlayerCombobox
          label="Maximo goleador"
          value={form.top_scorer_player_id}
          players={players}
          teamsById={teamsById}
          onChange={(v) => setForm((f) => ({ ...f, top_scorer_player_id: v }))}
          positionsAllowed={["DEL", "MED"]}
          placeholder="Buscar delantero o medio…"
        />
        <PlayerCombobox
          label="Mejor jugador"
          value={form.best_player_id}
          players={players}
          teamsById={teamsById}
          onChange={(v) => setForm((f) => ({ ...f, best_player_id: v }))}
          placeholder="Buscar jugador…"
        />
        <div>
          <label className="mb-1 block text-xs text-vpv-text-muted">Notas (opcional)</label>
          <textarea
            value={form.notes ?? ""}
            onChange={(e) =>
              setForm((f) => ({ ...f, notes: e.target.value || null }))
            }
            rows={3}
            maxLength={500}
            className="w-full rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
          />
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Step 2: Grupos — order 4 teams per group
// =============================================================================

function StepGrupos({
  form,
  updateBracket,
  teamsByGroup,
  disabled,
}: {
  form: PredictionRequest;
  updateBracket: (patch: Partial<BracketPredictions>) => void;
  teamsByGroup: Record<string, TeamOption[]>;
  disabled?: boolean;
}) {
  const groupLetters = Object.keys(teamsByGroup).sort();
  const groups = form.bracket_predictions?.groups ?? {};

  function setGroupOrder(letter: string, order: (number | null)[]) {
    updateBracket({
      groups: { ...groups, [letter]: order },
    });
  }

  if (groupLetters.length === 0) {
    return (
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-8 text-center">
        <p className="text-vpv-text-muted">
          Aun no hay equipos asignados a grupos. El admin debe configurarlos desde
          /admin/grupos antes de hacer predicciones.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-vpv-text-muted">
        Ordena los 4 equipos de cada grupo segun como crees que terminaran (1º a 4º).
      </p>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
        {groupLetters.map((letter) => (
          <GroupOrderCard
            key={letter}
            letter={letter}
            teams={teamsByGroup[letter]}
            order={groups[letter] ?? [null, null, null, null]}
            onChange={(o) => setGroupOrder(letter, o)}
            disabled={disabled}
          />
        ))}
      </div>
    </div>
  );
}

function GroupOrderCard({
  letter,
  teams,
  order,
  onChange,
  disabled,
}: {
  letter: string;
  teams: TeamOption[];
  order: (number | null)[];
  onChange: (order: (number | null)[]) => void;
  disabled?: boolean;
}) {
  // Build the visible 4-team order. If `order` is incomplete, fill remaining
  // slots with the rest of `teams` in original order so users can drag freely.
  const orderedTeams = useMemo<TeamOption[]>(() => {
    const seen = new Set<number>();
    const result: TeamOption[] = [];
    for (const id of order) {
      if (id == null) continue;
      const t = teams.find((x) => x.id === id);
      if (t && !seen.has(t.id)) {
        seen.add(t.id);
        result.push(t);
      }
    }
    for (const t of teams) {
      if (!seen.has(t.id)) {
        seen.add(t.id);
        result.push(t);
      }
    }
    return result.slice(0, 4);
  }, [teams, order]);

  const sensors = useSensors(
    useSensor(MouseSensor, { activationConstraint: { distance: 5 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIdx = orderedTeams.findIndex((t) => String(t.id) === String(active.id));
    const newIdx = orderedTeams.findIndex((t) => String(t.id) === String(over.id));
    if (oldIdx === -1 || newIdx === -1) return;
    const next = arrayMove(orderedTeams, oldIdx, newIdx);
    onChange(next.map((t) => t.id));
  }

  return (
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
      <div className="border-b border-vpv-border bg-vpv-bg/40 px-3 py-2 text-center">
        <h3 className="font-semibold text-vpv-text">Grupo {letter}</h3>
      </div>
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext
          items={orderedTeams.map((t) => String(t.id))}
          strategy={verticalListSortingStrategy}
        >
          <div className="space-y-1.5 px-3 py-2">
            {orderedTeams.map((t, idx) => (
              <SortableTeamCard
                key={t.id}
                id={String(t.id)}
                teamName={t.name}
                shortName={t.short_name}
                logoPath={t.logo_path}
                ordinal={["1º", "2º", "3º", "4º"][idx]}
                size="sm"
                disabled={disabled}
              />
            ))}
          </div>
        </SortableContext>
      </DndContext>
    </div>
  );
}

// =============================================================================
// Step 3: Eliminatoria — best thirds + bracket match winners
// =============================================================================

function StepEliminatoria({
  form,
  updateBracket,
  teamsById,
  teamsByGroup,
  bracket,
  disabled,
}: {
  form: PredictionRequest;
  updateBracket: (patch: Partial<BracketPredictions>) => void;
  teamsById: Record<number, TeamOption>;
  teamsByGroup: Record<string, TeamOption[]>;
  bracket: BracketResponse | null | undefined;
  disabled?: boolean;
}) {
  const groupOrders = form.bracket_predictions?.groups ?? {};
  const bestThirds = new Set(form.bracket_predictions?.best_thirds ?? []);
  const matchWinners = form.bracket_predictions?.match_winners ?? {};
  const groupLetters = Object.keys(teamsByGroup).sort();

  // FIFA WC 2026 Annex C: when the user has chosen the 8 advancing groups,
  // ask the backend which 3rd-of-group placeholder feeds each R32 match.
  // While bestThirds.size !== 8 the mapping is null and we fall back to the
  // "pick any candidate" combo behaviour.
  const [thirdPlaceMapping, setThirdPlaceMapping] = useState<
    Record<string, string> | null
  >(null);
  const bestThirdsKey = [...bestThirds].sort().join(",");

  useEffect(() => {
    let cancelled = false;
    if (bestThirds.size !== 8) {
      setThirdPlaceMapping(null);
      return;
    }
    (async () => {
      try {
        const res = await apiClient.post<{
          groups: string[];
          assignments: Record<string, string> | null;
        }>("/tournaments/third-place-assignments", {
          groups: [...bestThirds],
        });
        if (!cancelled) setThirdPlaceMapping(res.assignments ?? null);
      } catch {
        if (!cancelled) setThirdPlaceMapping(null);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bestThirdsKey]);

  function pickMatchWinner(code: string, teamId: number | null) {
    updateBracket({ match_winners: { ...matchWinners, [code]: teamId } });
  }

  // Resolve the candidate teams for a placeholder (1A, 2B, 3A, 3:ABCDF, Wxx, Lxx).
  // When matchCode is passed AND we have a third-place mapping, "3:XYZ" collapses
  // to a single fixed team according to the FIFA Annex C lookup.
  function resolveCandidates(
    placeholder: string | null | undefined,
    matchCode?: string | null,
  ): TeamOption[] {
    if (!placeholder) return [];
    // "1A" -> position 0; "2A" -> 1; "3A" -> 2 (used by the resolved mapping)
    if (/^[1-3][A-Z]$/.test(placeholder)) {
      const pos = Number(placeholder[0]) - 1;
      const letter = placeholder[1];
      const id = groupOrders[letter]?.[pos];
      if (id) return teamsById[id] ? [teamsById[id]] : [];
      return [];
    }
    // "3:ABCDF" -> any of the best-third teams from advancing groups.
    // If we already know the FIFA assignment for this match, collapse to one.
    if (placeholder.startsWith("3:")) {
      if (matchCode && thirdPlaceMapping?.[matchCode]) {
        return resolveCandidates(thirdPlaceMapping[matchCode]);
      }
      const candidateLetters = placeholder.slice(2).split("");
      const advancing = candidateLetters.filter((l) => bestThirds.has(l));
      return advancing
        .map((l) => groupOrders[l]?.[2])
        .filter((id): id is number => typeof id === "number")
        .map((id) => teamsById[id])
        .filter(Boolean);
    }
    // Wxx / Lxx -> winner / loser of previous match
    if (placeholder.startsWith("W")) {
      const code = `M${placeholder.slice(1)}`;
      const winner = matchWinners[code];
      if (winner) return teamsById[winner] ? [teamsById[winner]] : [];
      return [];
    }
    if (placeholder.startsWith("L")) {
      const code = `M${placeholder.slice(1)}`;
      const winner = matchWinners[code];
      // Loser is the OTHER team of that match. Find the match config for the loser.
      const otherMatch = bracket?.rounds
        .flatMap((r) => r.matches)
        .find((m) => m.match_code === code);
      if (!otherMatch) return [];
      const home = resolveCandidates(otherMatch.home_placeholder, code);
      const away = resolveCandidates(otherMatch.away_placeholder, code);
      const both = [...home, ...away];
      // Loser = the candidate that is NOT the winner
      return both.filter((t) => t.id !== winner);
    }
    return [];
  }

  if (!bracket || bracket.rounds.length === 0) {
    return (
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-8 text-center">
        <p className="text-vpv-text-muted">El bracket aun no esta configurado.</p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Best thirds */}
      <BestThirdsPicker
        groupLetters={groupLetters}
        bestThirds={bestThirds}
        teamsById={teamsById}
        groupOrders={groupOrders}
        onChange={(letters) => updateBracket({ best_thirds: letters })}
        disabled={disabled}
      />

      {/* Bracket: FIFA two-sided */}
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
        <div className="border-b border-vpv-border px-4 py-3">
          <h2 className="font-semibold text-vpv-text">Cuadro de eliminatorias</h2>
          <p className="text-xs text-vpv-text-muted">
            Click en el equipo para fijar el ganador (o mantén pulsado y arrastra).
          </p>
        </div>
        <InteractiveBracket
          bracket={bracket}
          resolveCandidates={resolveCandidates}
          matchWinners={matchWinners}
          onPick={pickMatchWinner}
          disabled={disabled}
        />
      </div>
    </div>
  );
}

// =============================================================================
// FIFA two-sided interactive bracket
// =============================================================================

type MatchByCode = Record<string, import("@/types").BracketMatch>;

interface InteractiveBracketProps {
  bracket: BracketResponse;
  resolveCandidates: (
    placeholder: string | null | undefined,
    matchCode?: string | null,
  ) => TeamOption[];
  matchWinners: Record<string, number | null>;
  onPick: (code: string, teamId: number | null) => void;
  disabled?: boolean;
}

function InteractiveBracket(props: InteractiveBracketProps) {
  const { bracket } = props;

  const matchByCode = useMemo<MatchByCode>(() => {
    const m: MatchByCode = {};
    for (const round of bracket.rounds) {
      for (const match of round.matches) {
        if (match.match_code) m[match.match_code] = match;
      }
    }
    return m;
  }, [bracket]);

  const layout = useMemo(() => computeBracketLayout(bracket, matchByCode), [bracket, matchByCode]);

  if (!layout) {
    return <InteractiveLinearBracket {...props} />;
  }

  return (
    <>
      {/* Desktop: two-sided */}
      <div className="hidden md:block">
        <InteractiveTwoSidedBracket layout={layout} matchByCode={matchByCode} {...props} />
      </div>
      {/* Mobile: linear stack */}
      <div className="md:hidden">
        <InteractiveLinearBracket {...props} />
      </div>
    </>
  );
}

interface BracketLayout {
  left: { r32: string[]; r16: string[]; qf: string[]; sf: string };
  right: { r32: string[]; r16: string[]; qf: string[]; sf: string };
  final: string;
  third: string | null;
}

function computeBracketLayout(
  data: BracketResponse,
  matchByCode: MatchByCode,
): BracketLayout | null {
  if (data.rounds.length < 2) return null;
  const lastIdx = data.rounds.length - 1;
  const finalRound = data.rounds[lastIdx];
  const semisRound = data.rounds[lastIdx - 1];
  if (!semisRound || semisRound.matches.length !== 2 || finalRound.matches.length === 0) return null;

  const semiL = semisRound.matches[0]?.match_code;
  const semiR = semisRound.matches[1]?.match_code;
  if (!semiL || !semiR) return null;

  function parents(code: string): [string, string] | null {
    const m = matchByCode[code];
    if (!m) return null;
    const h = parseParent(m.home_placeholder);
    const a = parseParent(m.away_placeholder);
    if (h && a) return [h, a];
    return null;
  }

  function trace(rootCode: string) {
    const qfPair = parents(rootCode);
    if (!qfPair) return null;
    const r16Codes: string[] = [];
    const r32Codes: string[] = [];
    for (const qf of qfPair) {
      const r16Pair = parents(qf);
      if (!r16Pair) return null;
      for (const r16 of r16Pair) {
        const r32Pair = parents(r16);
        if (!r32Pair) return null;
        for (const r32 of r32Pair) r32Codes.push(r32);
        r16Codes.push(r16);
      }
    }
    return { qf: qfPair, r16: r16Codes, r32: r32Codes };
  }

  const leftTrace = trace(semiL);
  const rightTrace = trace(semiR);
  if (!leftTrace || !rightTrace) return null;

  const finalCodes = finalRound.matches
    .map((m) => m.match_code ?? "")
    .filter(Boolean)
    .sort((a, b) => matchCodeNum(b) - matchCodeNum(a));
  const finalCode = finalCodes[0] ?? "";
  const thirdCode = finalCodes[1] ?? null;

  return {
    left: { ...leftTrace, sf: semiL },
    right: { ...rightTrace, sf: semiR },
    final: finalCode,
    third: thirdCode,
  };
}

function parseParent(p: string | null | undefined): string | null {
  if (!p) return null;
  if (p.startsWith("W") || p.startsWith("L")) return `M${p.slice(1)}`;
  return null;
}

function matchCodeNum(code: string): number {
  const m = /\d+/.exec(code);
  return m ? Number(m[0]) : 0;
}

function InteractiveTwoSidedBracket({
  layout,
  matchByCode,
  resolveCandidates,
  matchWinners,
  onPick,
  disabled,
}: InteractiveBracketProps & {
  layout: BracketLayout;
  matchByCode: MatchByCode;
}) {
  const renderColumn = (codes: string[], label: string, mdNum: number) => (
    <div className="flex min-w-[180px] flex-1 flex-col">
      <div className="mb-2 text-center text-[10px] font-semibold uppercase tracking-widest text-vpv-text-muted">
        {label} · J{mdNum}
      </div>
      <div className="flex h-full flex-col justify-around gap-3">
        {codes.map((code) => {
          const m = matchByCode[code];
          if (!m) {
            return (
              <div
                key={code}
                className="rounded border border-dashed border-vpv-border p-2 text-[10px] text-vpv-text-muted"
              >
                {code}
              </div>
            );
          }
          return (
            <InteractiveMatchCard
              key={code}
              match={m}
              resolveCandidates={resolveCandidates}
              winner={matchWinners[code] ?? null}
              onPick={onPick}
              disabled={disabled}
            />
          );
        })}
      </div>
    </div>
  );

  const roundNames = ["16avos", "Octavos", "Cuartos", "Semis", "Final"];
  const roundMatchdays = [4, 5, 6, 7, 8];

  return (
    <div className="overflow-x-auto p-3">
      <div className="flex min-h-[680px] items-stretch gap-2">
        {renderColumn(layout.left.r32, roundNames[0], roundMatchdays[0])}
        {renderColumn(layout.left.r16, roundNames[1], roundMatchdays[1])}
        {renderColumn(layout.left.qf, roundNames[2], roundMatchdays[2])}
        {renderColumn([layout.left.sf], roundNames[3], roundMatchdays[3])}

        {/* CENTER: Final + 3rd */}
        <div className="flex min-w-[210px] flex-col items-center justify-center gap-4 px-2">
          <div className="text-center text-[10px] font-semibold uppercase tracking-widest text-vpv-text-muted">
            {roundNames[4]} · J{roundMatchdays[4]}
          </div>
          {layout.final && matchByCode[layout.final] && (
            <div className="w-full rounded-lg border-2 border-amber-400/60 bg-gradient-to-br from-amber-500/10 to-amber-700/10 p-2 shadow-lg">
              <p className="mb-1 text-center text-[10px] font-semibold uppercase tracking-widest text-amber-400">
                🏆 Final
              </p>
              <InteractiveMatchCard
                match={matchByCode[layout.final]}
                resolveCandidates={resolveCandidates}
                winner={matchWinners[layout.final] ?? null}
                onPick={onPick}
                disabled={disabled}
                noFrame
              />
            </div>
          )}
          {layout.third && matchByCode[layout.third] && (
            <div className="w-full rounded-lg border border-zinc-500/30 bg-zinc-500/5 p-2">
              <p className="mb-1 text-center text-[10px] font-semibold uppercase tracking-wider text-vpv-text-muted">
                🥉 3er puesto
              </p>
              <InteractiveMatchCard
                match={matchByCode[layout.third]}
                resolveCandidates={resolveCandidates}
                winner={matchWinners[layout.third] ?? null}
                onPick={onPick}
                disabled={disabled}
                noFrame
              />
            </div>
          )}
        </div>

        {renderColumn([layout.right.sf], roundNames[3], roundMatchdays[3])}
        {renderColumn(layout.right.qf, roundNames[2], roundMatchdays[2])}
        {renderColumn(layout.right.r16, roundNames[1], roundMatchdays[1])}
        {renderColumn(layout.right.r32, roundNames[0], roundMatchdays[0])}
      </div>
    </div>
  );
}

function InteractiveLinearBracket({
  bracket,
  resolveCandidates,
  matchWinners,
  onPick,
  disabled,
}: InteractiveBracketProps) {
  return (
    <div className="space-y-4 p-3">
      {bracket.rounds.map((round) => (
        <div key={round.matchday}>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-vpv-text-muted">
            {round.name} · J{round.matchday}
          </h3>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {round.matches.map((m) => {
              if (!m.match_code) return null;
              return (
                <InteractiveMatchCard
                  key={m.match_code}
                  match={m}
                  resolveCandidates={resolveCandidates}
                  winner={matchWinners[m.match_code] ?? null}
                  onPick={onPick}
                  disabled={disabled}
                />
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

function InteractiveMatchCard({
  match,
  resolveCandidates,
  winner,
  onPick,
  noFrame,
  disabled,
}: {
  match: BracketResponse["rounds"][number]["matches"][number];
  resolveCandidates: (
    placeholder: string | null | undefined,
    matchCode?: string | null,
  ) => TeamOption[];
  winner: number | null;
  onPick: (code: string, teamId: number | null) => void;
  noFrame?: boolean;
  disabled?: boolean;
}) {
  const code = match.match_code!;
  const codeNum = code.replace(/^M/, "");
  const homes = resolveCandidates(match.home_placeholder, code);
  const aways = resolveCandidates(match.away_placeholder, code);
  const homeTeam = homes[0] ?? null;
  const awayTeam = aways[0] ?? null;
  const homeMulti = homes.length > 1;
  const awayMulti = aways.length > 1;

  const sensors = useSensors(
    useSensor(MouseSensor, { activationConstraint: { distance: 5 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 250, tolerance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  function handleDragEnd(event: DragEndEvent) {
    if (disabled) return;
    const { active, over } = event;
    if (!over) return;
    const targetId = String(over.id);
    if (targetId !== `match-${code}-home` && targetId !== `match-${code}-away`) return;
    const teamId = Number(String(active.id).replace(/^drag-\d+-\d+-/, ""));
    if (Number.isFinite(teamId)) onPick(code, teamId);
  }

  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
      <div
        className={
          noFrame
            ? "text-xs"
            : "rounded border border-vpv-border bg-vpv-bg/40 text-xs shadow-sm"
        }
      >
        {!noFrame && (
          <div className="border-b border-vpv-border/40 px-2 py-0.5 text-center text-[9px] font-semibold uppercase tracking-wider text-vpv-text-muted">
            {match.label ?? `Partido ${codeNum}`}
          </div>
        )}
        <BracketSlot
          dropId={`match-${code}-home`}
          slotCandidates={homes}
          slotMulti={homeMulti}
          team={homeTeam}
          isWinner={winner !== null && winner === homeTeam?.id}
          placeholder={match.home_placeholder}
          code={code}
          side="home"
          onPick={(id) => onPick(code, id)}
          disabled={disabled}
        />
        <div className="border-t border-vpv-border/30" />
        <BracketSlot
          dropId={`match-${code}-away`}
          slotCandidates={aways}
          slotMulti={awayMulti}
          team={awayTeam}
          isWinner={winner !== null && winner === awayTeam?.id}
          placeholder={match.away_placeholder}
          code={code}
          side="away"
          onPick={(id) => onPick(code, id)}
          disabled={disabled}
        />
      </div>
    </DndContext>
  );
}

function BracketSlot({
  dropId,
  slotCandidates,
  slotMulti,
  team,
  isWinner,
  placeholder,
  code,
  side,
  onPick,
  disabled,
}: {
  dropId: string;
  slotCandidates: TeamOption[];
  slotMulti: boolean;
  team: TeamOption | null;
  isWinner: boolean;
  placeholder: string | null | undefined;
  code: string;
  side: "home" | "away";
  onPick: (id: number | null) => void;
  disabled?: boolean;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: dropId });
  void side;

  // No candidate resolved yet → render placeholder text
  if (!team) {
    return (
      <div
        ref={setNodeRef}
        className={`flex items-center gap-1.5 px-2 py-1 transition-colors ${
          isOver ? "bg-vpv-accent/10" : ""
        }`}
      >
        <span className="text-[10px] italic text-vpv-text-muted">
          {placeholderLabel(placeholder)}
        </span>
      </div>
    );
  }

  // Multiple candidates (best 3rd unresolved) → render a select
  if (slotMulti) {
    return (
      <div ref={setNodeRef} className="px-2 py-1">
        <select
          value={isWinner ? team.id : ""}
          onChange={(e) => onPick(e.target.value ? Number(e.target.value) : null)}
          disabled={disabled}
          className="w-full rounded border border-vpv-border bg-vpv-card px-1 py-0.5 text-[10px] text-vpv-text"
        >
          <option value="">— elige —</option>
          {slotCandidates.map((t) => (
            <option key={t.id} value={t.id}>
              {t.short_name ?? t.name}
            </option>
          ))}
        </select>
      </div>
    );
  }

  // Single candidate → clickable + draggable chip
  return (
    <div
      ref={setNodeRef}
      className={`flex items-center gap-1.5 transition-colors ${
        isOver ? "bg-vpv-accent/10" : ""
      }`}
    >
      <DraggableTeamChip
        id={`drag-${code}-${team.id}-${team.id}`}
        team={team}
        isWinner={isWinner}
        onClick={() => onPick(isWinner ? null : team.id)}
        disabled={disabled}
      />
    </div>
  );
}

function DraggableTeamChip({
  id,
  team,
  isWinner,
  onClick,
  disabled,
}: {
  id: string;
  team: TeamOption;
  isWinner: boolean;
  onClick: () => void;
  disabled?: boolean;
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id,
    disabled,
  });
  const style: React.CSSProperties = {
    transform: CSS.Translate.toString(transform),
    opacity: isDragging ? 0.4 : 1,
    touchAction: "none",
  };
  return (
    <button
      ref={setNodeRef}
      type="button"
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      style={style}
      className={`flex w-full items-center gap-1.5 px-2 py-1 text-left transition-colors ${
        isWinner
          ? "bg-green-500/15 font-bold text-green-400"
          : "text-vpv-text hover:bg-vpv-bg"
      } ${disabled ? "cursor-not-allowed" : ""}`}
      aria-label={`Elegir o arrastrar ${team.name}`}
      {...(disabled ? {} : attributes)}
      {...(disabled ? {} : listeners)}
    >
      <CountryFlag teamName={team.name} fallbackLogo={team.logo_path} size={14} />
      <span className="min-w-0 flex-1 truncate text-[11px]">{team.short_name ?? team.name}</span>
      {isWinner && <span className="text-[10px]">✓</span>}
    </button>
  );
}

function placeholderLabel(p: string | null | undefined): string {
  if (!p) return "Por determinar";
  if (p.startsWith("1") && p.length === 2) return `1º Grupo ${p[1]}`;
  if (p.startsWith("2") && p.length === 2) return `2º Grupo ${p[1]}`;
  if (p.startsWith("3:")) return `Mejor 3º (${p.slice(2)})`;
  if (p.startsWith("W")) return `Ganador M${p.slice(1)}`;
  if (p.startsWith("L")) return `Perdedor M${p.slice(1)}`;
  return p;
}

// =============================================================================
// Read-only: all users' predictions
// =============================================================================

function AllPredictionsTable({
  data,
  loading,
  error,
  isAdmin,
  seasonId,
  onRecalculated,
}: {
  data: PredictionsListResponse | null | undefined;
  loading?: boolean;
  error?: boolean;
  isAdmin?: boolean;
  seasonId?: number | null;
  onRecalculated?: () => void | Promise<unknown>;
}) {
  const [recalcing, setRecalcing] = useState(false);
  const [recalcMsg, setRecalcMsg] = useState<string | null>(null);

  async function handleRecalc() {
    if (!seasonId) return;
    setRecalcing(true);
    setRecalcMsg(null);
    try {
      await apiClient.post(`/tournaments/admin/${seasonId}/predictions/recalculate`, {});
      setRecalcMsg("Puntos recalculados");
      await onRecalculated?.();
      setTimeout(() => setRecalcMsg(null), 3000);
    } catch {
      setRecalcMsg("Error al recalcular");
    } finally {
      setRecalcing(false);
    }
  }

  if (loading) {
    return (
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-4">
        <SkeletonCards count={2} />
      </div>
    );
  }
  if (error || !data) {
    return null;
  }
  if (data.predictions.length === 0) {
    return (
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-4 text-center text-sm text-vpv-text-muted">
        Aun no hay predicciones registradas.
      </div>
    );
  }
  return (
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
      <div className="flex items-center justify-between border-b border-vpv-border px-4 py-3">
        <h2 className="font-semibold text-vpv-text">Ranking de predicciones</h2>
        {isAdmin && (
          <div className="flex items-center gap-2">
            {recalcMsg && (
              <span className="text-xs text-vpv-text-muted">{recalcMsg}</span>
            )}
            <button
              onClick={handleRecalc}
              disabled={recalcing}
              className="rounded-md bg-vpv-accent px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50"
            >
              {recalcing ? "Recalculando..." : "Recalcular puntos"}
            </button>
          </div>
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-vpv-border bg-vpv-bg/50 text-xs text-vpv-text-muted">
              <th className="px-3 py-2 text-left">Participante</th>
              <th className="px-3 py-2 text-left">Campeon</th>
              <th className="px-3 py-2 text-left">Sorpresa</th>
              <th className="px-3 py-2 text-left">Goleador</th>
              <th className="px-3 py-2 text-right">Bonus</th>
            </tr>
          </thead>
          <tbody>
            {data.predictions.map((p) => (
              <tr
                key={p.id}
                className="border-b border-vpv-border last:border-0 hover:bg-vpv-bg/30"
              >
                <td className="px-3 py-2 font-medium text-vpv-text">{p.display_name ?? "—"}</td>
                <td className="px-3 py-2 text-vpv-text-muted">
                  <div className="flex items-center gap-1.5">
                    {p.winner_team_name && (
                      <CountryFlag teamName={p.winner_team_name} size={16} />
                    )}
                    {p.winner_team_name ?? "—"}
                  </div>
                </td>
                <td className="px-3 py-2 text-vpv-text-muted">
                  <div className="flex items-center gap-1.5">
                    {p.dark_horse_team_name && (
                      <CountryFlag teamName={p.dark_horse_team_name} size={16} />
                    )}
                    {p.dark_horse_team_name ?? "—"}
                  </div>
                </td>
                <td className="px-3 py-2 text-vpv-text-muted">{p.top_scorer_player_name ?? "—"}</td>
                <td className="px-3 py-2 text-right font-bold tabular-nums text-vpv-text">{p.bonus_points}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// =============================================================================
// Small reusable bits
// =============================================================================

// PlayerCombobox: typeahead search over the prediction's player pool
// (≈1 200 players for a Mundial). Filters by accent-insensitive name and
// by VPV position, renders the player's photo + position badge + national
// flag of the team. Replaces a plain <select> that scrolled forever.

function _norm(value: string): string {
  return value.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();
}

const POS_BADGE: Record<string, string> = {
  POR: "bg-yellow-500/20 text-yellow-300",
  DEF: "bg-blue-500/20 text-blue-300",
  MED: "bg-green-500/20 text-green-300",
  DEL: "bg-red-500/20 text-red-300",
};

function PlayerCombobox({
  label,
  value,
  players,
  teamsById,
  onChange,
  positionsAllowed,
  placeholder = "Buscar jugador...",
}: {
  label: string;
  value: number | null;
  players: PlayerOption[];
  teamsById: Record<number, TeamOption>;
  onChange: (v: number | null) => void;
  // When set, restrict the dropdown to these VPV positions (e.g. ["DEL", "MED"]
  // for "Máximo goleador"). null/undefined → no restriction.
  positionsAllowed?: string[] | null;
  placeholder?: string;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Close the dropdown when clicking outside.
  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  const selected = value ? players.find((p) => p.id === value) ?? null : null;
  const selectedTeam = selected ? teamsById[selected.team_id] ?? null : null;

  const normQuery = _norm(query.trim());

  const filtered = useMemo(() => {
    const allowed = positionsAllowed?.length
      ? new Set(positionsAllowed.map((p) => p.toUpperCase()))
      : null;
    return players
      .filter((p) => {
        if (allowed && (!p.position || !allowed.has(p.position.toUpperCase()))) {
          return false;
        }
        if (!normQuery) return true;
        return (
          _norm(p.name).includes(normQuery) ||
          _norm(p.team_name).includes(normQuery)
        );
      })
      .slice(0, 30);
  }, [players, normQuery, positionsAllowed]);

  function pick(player: PlayerOption) {
    onChange(player.id);
    setQuery("");
    setOpen(false);
  }

  return (
    <div ref={containerRef} className="relative">
      <label className="mb-1 block text-xs text-vpv-text-muted">{label}</label>
      {selected ? (
        <div className="flex items-center gap-2 rounded border border-vpv-border bg-vpv-bg px-2 py-1.5">
          <PlayerAvatar
            photoPath={selected.photo_path}
            name={selected.name}
            size={28}
          />
          {selected.position && (
            <span
              className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${POS_BADGE[selected.position] ?? ""}`}
            >
              {selected.position}
            </span>
          )}
          <span className="flex-1 truncate text-sm text-vpv-text">
            {selected.name}
          </span>
          {selectedTeam && (
            <CountryFlag
              teamName={selectedTeam.name}
              fallbackLogo={selectedTeam.logo_path}
              size={20}
            />
          )}
          <span className="hidden text-xs text-vpv-text-muted sm:inline">
            {selected.team_name}
          </span>
          <button
            type="button"
            onClick={() => {
              onChange(null);
              setQuery("");
            }}
            className="ml-1 inline-flex h-6 w-6 items-center justify-center rounded text-vpv-text-muted hover:bg-red-500/15 hover:text-red-500"
            aria-label="Quitar selección"
          >
            ✕
          </button>
        </div>
      ) : (
        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          placeholder={placeholder}
          className="w-full rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
        />
      )}

      {!selected && open && (
        <div className="absolute z-30 mt-1 max-h-72 w-full overflow-auto rounded-lg border border-vpv-card-border bg-vpv-card shadow-lg">
          {filtered.length === 0 ? (
            <p className="px-3 py-2 text-xs text-vpv-text-muted">
              Sin resultados
            </p>
          ) : (
            filtered.map((p) => {
              const team = teamsById[p.team_id];
              return (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => pick(p)}
                  className="flex w-full items-center gap-2 px-2 py-1.5 text-left transition-colors hover:bg-vpv-bg"
                >
                  <PlayerAvatar
                    photoPath={p.photo_path}
                    name={p.name}
                    size={24}
                  />
                  {p.position && (
                    <span
                      className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${POS_BADGE[p.position] ?? ""}`}
                    >
                      {p.position}
                    </span>
                  )}
                  <span className="flex-1 truncate text-sm text-vpv-text">
                    {p.name}
                  </span>
                  {team && (
                    <CountryFlag
                      teamName={team.name}
                      fallbackLogo={team.logo_path}
                      size={18}
                    />
                  )}
                  <span className="hidden text-xs text-vpv-text-muted md:inline">
                    {p.team_name}
                  </span>
                </button>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}

function FormSelect({
  label,
  value,
  options,
  onChange,
  preview,
}: {
  label: string;
  value: number | null;
  options: { id: number; label: string }[];
  onChange: (v: number | null) => void;
  preview?: React.ReactNode;
}) {
  return (
    <div>
      <label className="mb-1 block text-xs text-vpv-text-muted">{label}</label>
      <div className="flex items-center gap-2">
        {preview && <span className="shrink-0">{preview}</span>}
        <select
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
          className="w-full flex-1 rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
        >
          <option value="">— Seleccionar —</option>
          {options.map((o) => (
            <option key={o.id} value={o.id}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

// =============================================================================
// Best Thirds drag & drop picker
// =============================================================================

function BestThirdsPicker({
  groupLetters,
  bestThirds,
  teamsById,
  groupOrders,
  onChange,
  disabled,
}: {
  groupLetters: string[];
  bestThirds: Set<string>;
  teamsById: Record<number, TeamOption>;
  groupOrders: Record<string, (number | null)[]>;
  onChange: (letters: string[]) => void;
  disabled?: boolean;
}) {
  const chosen = [...bestThirds].sort();
  const available = groupLetters.filter((l) => !bestThirds.has(l));
  const max = 8;
  const full = chosen.length >= max;

  const sensors = useSensors(
    useSensor(MouseSensor, { activationConstraint: { distance: 5 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  function handleDragEnd(event: DragEndEvent) {
    if (disabled) return;
    const { active, over } = event;
    if (!over) return;
    const letter = String(active.id).replace(/^(chosen|available)-/, "");
    const overId = String(over.id);
    const overContainer = overId.startsWith("chosen") ? "chosen" : "available";
    const fromContainer = bestThirds.has(letter) ? "chosen" : "available";

    if (fromContainer === overContainer) return; // no-op (reorder inside same column)

    const next = new Set(bestThirds);
    if (overContainer === "chosen") {
      if (next.size < max) next.add(letter);
    } else {
      next.delete(letter);
    }
    onChange([...next].sort());
  }

  function ThirdCard({ letter }: { letter: string }) {
    const team = groupOrders[letter]?.[2] ? teamsById[groupOrders[letter]![2]!] : null;
    return (
      <SortableTeamCard
        id={`${bestThirds.has(letter) ? "chosen" : "available"}-${letter}`}
        teamName={team?.name ?? `Grupo ${letter}`}
        shortName={team?.short_name}
        logoPath={team?.logo_path}
        ordinal={letter}
        size="sm"
        disabled={disabled}
      />
    );
  }

  return (
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
      <div className="border-b border-vpv-border px-4 py-3">
        <h2 className="font-semibold text-vpv-text">Mejores 3os clasificados</h2>
        <p className="text-xs text-vpv-text-muted">
          Arrastra los grupos cuyo 3º clasificado pasara a 16avos.{" "}
          <span className={chosen.length === max ? "text-green-500" : "text-amber-500"}>
            {chosen.length} / {max}
          </span>
        </p>
      </div>
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <div className="grid grid-cols-1 gap-3 p-3 md:grid-cols-2">
          <DroppableColumn
            id="chosen-zone"
            title={`Clasifican (${chosen.length}/${max})`}
            highlight={!full}
            items={chosen.map((l) => `chosen-${l}`)}
          >
            {chosen.length === 0 ? (
              <p className="py-4 text-center text-xs text-vpv-text-muted/60">
                Arrastra aquí los 8 grupos
              </p>
            ) : (
              chosen.map((letter) => <ThirdCard key={letter} letter={letter} />)
            )}
          </DroppableColumn>
          <DroppableColumn
            id="available-zone"
            title="Disponibles"
            items={available.map((l) => `available-${l}`)}
          >
            {available.length === 0 ? (
              <p className="py-4 text-center text-xs text-vpv-text-muted/60">
                Todos los grupos asignados
              </p>
            ) : (
              available.map((letter) => <ThirdCard key={letter} letter={letter} />)
            )}
          </DroppableColumn>
        </div>
      </DndContext>
    </div>
  );
}

function DroppableColumn({
  id,
  title,
  items,
  highlight,
  children,
}: {
  id: string;
  title: string;
  items: string[];
  highlight?: boolean;
  children: React.ReactNode;
}) {
  const { setNodeRef, isOver } = useDroppable({ id });
  return (
    <SortableContext items={items} strategy={verticalListSortingStrategy}>
      <div
        ref={setNodeRef}
        className={`rounded-md border-2 p-2 transition-colors ${
          isOver && highlight !== false
            ? "border-vpv-accent/60 bg-vpv-accent/5"
            : "border-dashed border-vpv-border bg-vpv-bg/40"
        }`}
      >
        <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-vpv-text-muted">
          {title}
        </p>
        <div className="space-y-1.5">{children}</div>
      </div>
    </SortableContext>
  );
}
