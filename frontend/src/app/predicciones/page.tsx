"use client";

import { useEffect, useState } from "react";
import { useSeason } from "@/contexts/season-context";
import { useFetch } from "@/hooks/use-fetch";
import { apiClient } from "@/lib/api-client";
import { SkeletonCards } from "@/components/ui/skeleton";
import type {
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
  const seasonId = selectedSeason?.id ?? null;

  const { data: teams } = useFetch<TeamOption[]>(
    seasonId ? `/tournaments/${seasonId}/teams` : null,
  );
  const { data: players } = useFetch<PlayerOption[]>(
    seasonId ? `/tournaments/${seasonId}/players` : null,
  );
  const { data: myPred } = useFetch<TournamentPrediction | null>(
    seasonId ? `/tournaments/${seasonId}/predictions/me` : null,
  );
  const { data: allPreds, loading: loadingAll, refetch: refetchAll } = useFetch<PredictionsListResponse>(
    seasonId ? `/tournaments/${seasonId}/predictions` : null,
  );

  const [form, setForm] = useState<PredictionRequest>({
    winner_team_id: null,
    top_scorer_player_id: null,
    best_player_id: null,
    dark_horse_team_id: null,
    notes: null,
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
      await refetchAll();
      setTimeout(() => setMessage(null), 3000);
    } catch {
      setMessage("Error al guardar");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-vpv-text">Predicciones</h1>
        <p className="mt-1 text-vpv-text-muted">
          Acierta el campeon, maximo goleador, mejor jugador y la sorpresa del torneo.
        </p>
      </div>

      {/* My prediction form */}
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
        <div className="border-b border-vpv-border px-4 py-3">
          <h2 className="font-semibold text-vpv-text">Mi prediccion</h2>
        </div>
        <div className="space-y-3 px-4 py-3">
          <FormSelect
            label="Campeon del torneo"
            value={form.winner_team_id}
            options={(teams ?? []).map((t) => ({ id: t.id, label: t.name }))}
            onChange={(v) => setForm((f) => ({ ...f, winner_team_id: v }))}
          />
          <FormSelect
            label="Sorpresa del torneo"
            value={form.dark_horse_team_id}
            options={(teams ?? []).map((t) => ({ id: t.id, label: t.name }))}
            onChange={(v) => setForm((f) => ({ ...f, dark_horse_team_id: v }))}
          />
          <FormSelect
            label="Maximo goleador"
            value={form.top_scorer_player_id}
            options={(players ?? []).map((p) => ({
              id: p.id,
              label: `${p.name} (${p.team_name})`,
            }))}
            onChange={(v) => setForm((f) => ({ ...f, top_scorer_player_id: v }))}
          />
          <FormSelect
            label="Mejor jugador"
            value={form.best_player_id}
            options={(players ?? []).map((p) => ({
              id: p.id,
              label: `${p.name} (${p.team_name})`,
            }))}
            onChange={(v) => setForm((f) => ({ ...f, best_player_id: v }))}
          />
          <div>
            <label className="mb-1 block text-xs text-vpv-text-muted">
              Notas (opcional)
            </label>
            <textarea
              value={form.notes ?? ""}
              onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value || null }))}
              rows={3}
              maxLength={500}
              placeholder="Tu opinion, predicciones extra, etc."
              className="w-full rounded border border-vpv-border bg-vpv-bg px-2 py-1.5 text-sm text-vpv-text"
            />
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleSave}
              disabled={saving}
              className="rounded bg-vpv-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-vpv-accent/80 disabled:opacity-50"
            >
              {saving ? "Guardando..." : "Guardar prediccion"}
            </button>
            {message && (
              <span className="text-xs text-vpv-text-muted">{message}</span>
            )}
          </div>
        </div>
      </div>

      {/* All predictions */}
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
        <div className="border-b border-vpv-border px-4 py-3">
          <h2 className="font-semibold text-vpv-text">
            Predicciones de todos
          </h2>
        </div>
        {loadingAll ? (
          <div className="p-4">
            <SkeletonCards count={3} />
          </div>
        ) : !allPreds || allPreds.predictions.length === 0 ? (
          <p className="px-4 py-6 text-center text-sm text-vpv-text-muted">
            Aun no hay predicciones registradas.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-vpv-border bg-vpv-bg/50 text-xs text-vpv-text-muted">
                  <th className="px-3 py-2 text-left">Participante</th>
                  <th className="px-3 py-2 text-left">Campeon</th>
                  <th className="px-3 py-2 text-left">Sorpresa</th>
                  <th className="px-3 py-2 text-left">Goleador</th>
                  <th className="px-3 py-2 text-left">Mejor jugador</th>
                  <th className="px-3 py-2 text-right">Bonus</th>
                </tr>
              </thead>
              <tbody>
                {allPreds.predictions.map((p) => (
                  <tr
                    key={p.id}
                    className="border-b border-vpv-border last:border-0 hover:bg-vpv-bg/30"
                  >
                    <td className="px-3 py-2 font-medium text-vpv-text">
                      {p.display_name ?? "—"}
                    </td>
                    <td className="px-3 py-2 text-vpv-text-muted">
                      {p.winner_team_name ?? "—"}
                    </td>
                    <td className="px-3 py-2 text-vpv-text-muted">
                      {p.dark_horse_team_name ?? "—"}
                    </td>
                    <td className="px-3 py-2 text-vpv-text-muted">
                      {p.top_scorer_player_name ?? "—"}
                    </td>
                    <td className="px-3 py-2 text-vpv-text-muted">
                      {p.best_player_name ?? "—"}
                    </td>
                    <td className="px-3 py-2 text-right font-bold tabular-nums text-vpv-text">
                      {p.bonus_points}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

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
