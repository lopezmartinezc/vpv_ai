"use client";

import { useEffect, useMemo, useState } from "react";
import { useSeason } from "@/contexts/season-context";
import { useAuth } from "@/contexts/auth-context";
import { useFetch } from "@/hooks/use-fetch";
import { apiClient } from "@/lib/api-client";
import { SkeletonCards } from "@/components/ui/skeleton";
import { TournamentHero } from "@/components/tournament/tournament-hero";
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
  const { data: allPreds, refetch: refetchAll } = useFetch<PredictionsListResponse>(
    seasonId ? `/tournaments/${seasonId}/predictions` : null,
  );
  const { data: bracket } = useFetch<BracketResponse>(
    seasonId ? `/tournaments/${seasonId}/bracket` : null,
  );

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
        title="Predicciones"
        subtitle="Acierta los grupos, eliminatorias y premios"
      />

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
          <button
            onClick={handleSave}
            disabled={saving}
            className="rounded bg-vpv-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-vpv-accent/80 disabled:opacity-50"
          >
            {saving ? "Guardando..." : "Guardar"}
          </button>
        </div>
      </div>

      {step === "generales" && (
        <StepGenerales form={form} setForm={setForm} teams={teams ?? []} players={players ?? []} />
      )}
      {step === "grupos" && (
        <StepGrupos
          form={form}
          updateBracket={updateBracket}
          teamsByGroup={teamsByGroup}
        />
      )}
      {step === "eliminatoria" && (
        <StepEliminatoria
          form={form}
          updateBracket={updateBracket}
          teamsById={teamsById}
          teamsByGroup={teamsByGroup}
          bracket={bracket}
        />
      )}

      {/* Resumen ranking de predicciones */}
      <AllPredictionsTable
        data={allPreds}
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
        />
        <FormSelect
          label="Sorpresa del torneo"
          value={form.dark_horse_team_id}
          options={teams.map((t) => ({ id: t.id, label: t.name }))}
          onChange={(v) => setForm((f) => ({ ...f, dark_horse_team_id: v }))}
        />
        <FormSelect
          label="Maximo goleador"
          value={form.top_scorer_player_id}
          options={players.map((p) => ({ id: p.id, label: `${p.name} (${p.team_name})` }))}
          onChange={(v) => setForm((f) => ({ ...f, top_scorer_player_id: v }))}
        />
        <FormSelect
          label="Mejor jugador"
          value={form.best_player_id}
          options={players.map((p) => ({ id: p.id, label: `${p.name} (${p.team_name})` }))}
          onChange={(v) => setForm((f) => ({ ...f, best_player_id: v }))}
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
}: {
  form: PredictionRequest;
  updateBracket: (patch: Partial<BracketPredictions>) => void;
  teamsByGroup: Record<string, TeamOption[]>;
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
}: {
  letter: string;
  teams: TeamOption[];
  order: (number | null)[];
  onChange: (order: (number | null)[]) => void;
}) {
  // Build candidates: teams in this group, minus those already used in another slot
  function candidatesFor(slotIdx: number): TeamOption[] {
    const usedElsewhere = new Set(
      order.filter((_, i) => i !== slotIdx).filter((id): id is number => id !== null),
    );
    return teams.filter((t) => !usedElsewhere.has(t.id));
  }

  return (
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
      <div className="border-b border-vpv-border bg-vpv-bg/40 px-3 py-2 text-center">
        <h3 className="font-semibold text-vpv-text">Grupo {letter}</h3>
      </div>
      <div className="space-y-1.5 px-3 py-2 text-xs">
        {[0, 1, 2, 3].map((idx) => {
          const ordinal = ["1º", "2º", "3º", "4º"][idx];
          const value = order[idx] ?? "";
          return (
            <div key={idx} className="flex items-center gap-2">
              <span className="w-6 shrink-0 font-semibold text-vpv-text-muted">{ordinal}</span>
              <select
                value={value}
                onChange={(e) => {
                  const newOrder = [...order];
                  newOrder[idx] = e.target.value ? Number(e.target.value) : null;
                  onChange(newOrder);
                }}
                className="flex-1 rounded border border-vpv-border bg-vpv-bg px-1.5 py-1 text-vpv-text"
              >
                <option value="">—</option>
                {candidatesFor(idx).map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </div>
          );
        })}
      </div>
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
}: {
  form: PredictionRequest;
  updateBracket: (patch: Partial<BracketPredictions>) => void;
  teamsById: Record<number, TeamOption>;
  teamsByGroup: Record<string, TeamOption[]>;
  bracket: BracketResponse | null | undefined;
}) {
  const groupOrders = form.bracket_predictions?.groups ?? {};
  const bestThirds = new Set(form.bracket_predictions?.best_thirds ?? []);
  const matchWinners = form.bracket_predictions?.match_winners ?? {};
  const groupLetters = Object.keys(teamsByGroup).sort();

  function toggleThird(letter: string) {
    const next = new Set(bestThirds);
    if (next.has(letter)) next.delete(letter);
    else if (next.size < 8) next.add(letter);
    updateBracket({ best_thirds: Array.from(next).sort() });
  }

  function pickMatchWinner(code: string, teamId: number | null) {
    updateBracket({ match_winners: { ...matchWinners, [code]: teamId } });
  }

  // Resolve the candidate teams for a placeholder (1A, 2B, 3:ABCDF, Wxx, Lxx)
  function resolveCandidates(placeholder: string | null | undefined): TeamOption[] {
    if (!placeholder) return [];
    // "1A" -> position 0 of group A; "2A" -> position 1
    if (/^[12][A-Z]$/.test(placeholder)) {
      const pos = Number(placeholder[0]) - 1;
      const letter = placeholder[1];
      const id = groupOrders[letter]?.[pos];
      if (id) return teamsById[id] ? [teamsById[id]] : [];
      return [];
    }
    // "3:ABCDF" -> any of the best-third teams from groups that the user picked as advancing
    if (placeholder.startsWith("3:")) {
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
      const home = resolveCandidates(otherMatch.home_placeholder);
      const away = resolveCandidates(otherMatch.away_placeholder);
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
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
        <div className="border-b border-vpv-border px-4 py-3">
          <h2 className="font-semibold text-vpv-text">Mejores 3os clasificados</h2>
          <p className="text-xs text-vpv-text-muted">
            Marca los 8 grupos cuyo 3er clasificado pasara a 16avos.{" "}
            <span className={bestThirds.size === 8 ? "text-green-500" : "text-amber-500"}>
              {bestThirds.size} / 8
            </span>
          </p>
        </div>
        <div className="grid grid-cols-3 gap-2 p-3 sm:grid-cols-4 md:grid-cols-6">
          {groupLetters.map((letter) => {
            const team = groupOrders[letter]?.[2]
              ? teamsById[groupOrders[letter]![2]!]
              : null;
            const checked = bestThirds.has(letter);
            const disabled = !checked && bestThirds.size >= 8;
            return (
              <button
                key={letter}
                type="button"
                onClick={() => toggleThird(letter)}
                disabled={disabled}
                className={`flex items-center gap-2 rounded border px-2 py-1.5 text-xs transition-colors ${
                  checked
                    ? "border-green-500/50 bg-green-500/10 text-green-400"
                    : disabled
                      ? "border-vpv-border bg-vpv-bg opacity-40"
                      : "border-vpv-border bg-vpv-bg text-vpv-text-muted hover:border-vpv-accent"
                }`}
              >
                <span className="font-bold">{letter}</span>
                {team?.logo_path && <img src={team.logo_path} alt="" className="h-4 w-4" />}
                <span className="min-w-0 flex-1 truncate text-left">
                  {team ? team.short_name ?? team.name : "(sin 3º)"}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Bracket: rounds */}
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
        <div className="border-b border-vpv-border px-4 py-3">
          <h2 className="font-semibold text-vpv-text">Cuadro de eliminatorias</h2>
          <p className="text-xs text-vpv-text-muted">
            Haz click en el equipo que crees que pasara en cada partido.
          </p>
        </div>
        <div className="space-y-5 p-4">
          {bracket.rounds.map((round) => (
            <div key={round.matchday}>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-vpv-text-muted">
                {round.name} · J{round.matchday}
              </h3>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
                {round.matches.map((m) => {
                  if (!m.match_code) return null;
                  const homes = resolveCandidates(m.home_placeholder);
                  const aways = resolveCandidates(m.away_placeholder);
                  const winner = matchWinners[m.match_code] ?? null;
                  return (
                    <PickableMatch
                      key={m.match_code}
                      code={m.match_code}
                      label={m.label}
                      homes={homes}
                      aways={aways}
                      winner={winner}
                      onPick={(id) => pickMatchWinner(m.match_code!, id)}
                    />
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function PickableMatch({
  code,
  label,
  homes,
  aways,
  winner,
  onPick,
}: {
  code: string;
  label?: string | null;
  homes: TeamOption[];
  aways: TeamOption[];
  winner: number | null;
  onPick: (id: number | null) => void;
}) {
  const codeNum = code.replace(/^M/, "");
  return (
    <div className="rounded border border-vpv-border bg-vpv-bg/40 text-xs">
      <div className="border-b border-vpv-border/40 px-2 py-0.5 text-center text-[9px] font-semibold uppercase tracking-wider text-vpv-text-muted">
        {label ?? `Partido ${codeNum}`}
      </div>
      <CandidatePicker
        side="home"
        candidates={homes}
        selected={winner}
        onPick={onPick}
      />
      <div className="border-t border-vpv-border/30 px-2 py-0.5 text-center text-[9px] uppercase text-vpv-text-muted">
        vs
      </div>
      <CandidatePicker
        side="away"
        candidates={aways}
        selected={winner}
        onPick={onPick}
      />
    </div>
  );
}

function CandidatePicker({
  side,
  candidates,
  selected,
  onPick,
}: {
  side: "home" | "away";
  candidates: TeamOption[];
  selected: number | null;
  onPick: (id: number | null) => void;
}) {
  if (candidates.length === 0) {
    return (
      <div className="px-2 py-1 text-[10px] italic text-vpv-text-muted">Por determinar</div>
    );
  }
  if (candidates.length === 1) {
    const t = candidates[0];
    const isSelected = selected === t.id;
    return (
      <button
        type="button"
        onClick={() => onPick(isSelected ? null : t.id)}
        className={`flex w-full items-center gap-1.5 px-2 py-1 transition-colors ${
          isSelected
            ? "bg-green-500/15 font-bold text-green-400"
            : "text-vpv-text hover:bg-vpv-bg"
        }`}
        aria-label={`Pick ${t.name} (${side})`}
      >
        {t.logo_path && <img src={t.logo_path} alt="" className="h-4 w-4" />}
        <span className="min-w-0 flex-1 truncate text-left">{t.short_name ?? t.name}</span>
        {isSelected && <span className="text-[10px]">✓</span>}
      </button>
    );
  }
  // Multiple candidates (e.g. best 3rd unresolved): select one
  return (
    <div className="px-2 py-1">
      <select
        value={selected ?? ""}
        onChange={(e) => onPick(e.target.value ? Number(e.target.value) : null)}
        className="w-full rounded border border-vpv-border bg-vpv-card px-1 py-0.5 text-[10px] text-vpv-text"
      >
        <option value="">—</option>
        {candidates.map((t) => (
          <option key={t.id} value={t.id}>
            {t.short_name ?? t.name}
          </option>
        ))}
      </select>
    </div>
  );
}

// =============================================================================
// Read-only: all users' predictions
// =============================================================================

function AllPredictionsTable({
  data,
  isAdmin,
  seasonId,
  onRecalculated,
}: {
  data: PredictionsListResponse | null | undefined;
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

  if (!data) {
    return (
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-4">
        <SkeletonCards count={2} />
      </div>
    );
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
                <td className="px-3 py-2 text-vpv-text-muted">{p.winner_team_name ?? "—"}</td>
                <td className="px-3 py-2 text-vpv-text-muted">{p.dark_horse_team_name ?? "—"}</td>
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

function FormSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: number | null;
  options: { id: number; label: string }[];
  onChange: (v: number | null) => void;
}) {
  return (
    <div>
      <label className="mb-1 block text-xs text-vpv-text-muted">{label}</label>
      <select
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
        className="w-full rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
      >
        <option value="">— Seleccionar —</option>
        {options.map((o) => (
          <option key={o.id} value={o.id}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}
