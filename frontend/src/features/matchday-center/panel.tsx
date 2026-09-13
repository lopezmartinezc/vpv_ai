"use client";

import { useCallback, useEffect, useState, type ReactElement } from "react";
import Link from "next/link";
import { apiClient } from "@/lib/api-client";
import type { CloseReport, MatchdayState } from "@/types";
import {
  closeAllowed,
  closeMovesMoney,
  gapsOf,
  headline,
  hiddenExampleCount,
  shownExamples,
} from "./gaps";

const OUTCOME_STYLE: Record<string, string> = {
  hecho: "border-emerald-500/40 bg-emerald-500/10 text-emerald-400",
  ya_estaba: "border-vpv-card-border bg-vpv-bg text-vpv-text-muted",
  bloqueado: "border-amber-500/40 bg-amber-500/10 text-amber-400",
};
const OUTCOME_LABEL: Record<string, string> = {
  hecho: "hará",
  ya_estaba: "ya estaba",
  bloqueado: "bloqueado",
};

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? "—"
    : d.toLocaleString("es-ES", { dateStyle: "short", timeStyle: "short" });
}

export function MatchdayCenterPanel({
  seasonId,
  matchdayNumber,
}: {
  seasonId: number;
  matchdayNumber: number;
}): ReactElement {
  const [state, setState] = useState<MatchdayState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [closing, setClosing] = useState(false);
  const [result, setResult] = useState<CloseReport | null>(null);
  const [confirming, setConfirming] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setState(
        await apiClient.get<MatchdayState>(
          `/matchdays/admin/${seasonId}/${matchdayNumber}/estado`,
        ),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo leer el estado de la jornada");
    } finally {
      setLoading(false);
    }
  }, [seasonId, matchdayNumber]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleClose() {
    setClosing(true);
    setError(null);
    try {
      const report = await apiClient.post<CloseReport>(
        `/matchdays/admin/${seasonId}/${matchdayNumber}/cerrar`,
        {},
      );
      setResult(report);
      setConfirming(false);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo cerrar la jornada");
    } finally {
      setClosing(false);
    }
  }

  if (loading && !state) {
    return (
      <div className="flex min-h-[30vh] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-vpv-accent border-t-transparent" />
      </div>
    );
  }

  if (error && !state) {
    return (
      <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
        {error}
      </div>
    );
  }

  if (!state) return <></>;

  const gaps = gapsOf(state);
  const allowed = closeAllowed(state);
  const movesMoney = closeMovesMoney(state);

  return (
    <div className="space-y-5">
      <header className="rounded-lg border border-vpv-card-border bg-vpv-card p-5">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-lg font-semibold text-vpv-text">
            Jornada {state.matchday_number}
            {state.is_current && (
              <span className="ml-2 rounded-full border border-vpv-accent/40 bg-vpv-accent/10 px-2 py-0.5 text-[10px] font-medium text-vpv-accent">
                actual
              </span>
            )}
          </h2>
          <p
            className={`text-sm font-medium ${
              state.status === "finished"
                ? "text-vpv-text-muted"
                : allowed
                  ? "text-emerald-400"
                  : "text-amber-400"
            }`}
          >
            {headline(state)}
          </p>
        </div>
        <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-xs md:grid-cols-4">
          {[
            ["Estado", state.status],
            ["Partidos que cuentan", `${state.matches_counting} de ${state.matches_total}`],
            ["Cierre de alineaciones", formatDate(state.deadline_at)],
            ["Último scraping", formatDate(state.last_scrape_at)],
          ].map(([label, value]) => (
            <div key={label}>
              <dt className="text-vpv-text-muted">{label}</dt>
              <dd className="font-medium text-vpv-text tabular-nums">{value}</dd>
            </div>
          ))}
        </dl>
      </header>

      <section className="rounded-lg border border-vpv-card-border bg-vpv-card p-5">
        <h3 className="mb-3 text-sm font-semibold text-vpv-text">Qué falta</h3>
        {gaps.length === 0 ? (
          <p className="text-sm text-vpv-text-muted">
            Nada pendiente en esta jornada.
          </p>
        ) : (
          <ul className="space-y-2">
            {gaps.map((gap) => (
              <li
                key={gap.id}
                className={`flex flex-wrap items-center justify-between gap-2 rounded-md border px-3 py-2 ${
                  gap.blocking
                    ? "border-amber-500/40 bg-amber-500/10"
                    : "border-vpv-card-border bg-vpv-bg"
                }`}
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium text-vpv-text">
                    {gap.label}
                    <span className="ml-2 tabular-nums text-vpv-text-muted">{gap.count}</span>
                    {gap.blocking && (
                      <span className="ml-2 text-[10px] font-medium uppercase tracking-wide text-amber-400">
                        impide cerrar
                      </span>
                    )}
                  </p>
                  {gap.examples.length > 0 && (
                    <p className="truncate text-xs text-vpv-text-muted">
                      {shownExamples(gap).join(", ")}
                      {hiddenExampleCount(gap) > 0 && ` y ${hiddenExampleCount(gap)} más`}
                    </p>
                  )}
                </div>
                <Link
                  href={gap.href}
                  className="shrink-0 rounded-md border border-vpv-border px-2.5 py-1 text-xs font-medium text-vpv-text transition-colors hover:bg-vpv-card"
                >
                  Resolver
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-lg border border-vpv-card-border bg-vpv-card p-5">
        <h3 className="mb-1 text-sm font-semibold text-vpv-text">
          Qué pasaría al cerrar
        </h3>
        <p className="mb-3 text-xs text-vpv-text-muted">
          Calculado por el servidor sin ejecutar nada.
        </p>
        <ul className="space-y-1.5">
          {state.preview.steps.map((step) => (
            <li key={step.name} className="flex flex-wrap items-center gap-2 text-sm">
              <span
                className={`shrink-0 rounded border px-1.5 py-px text-[10px] font-medium ${
                  OUTCOME_STYLE[step.outcome] ?? OUTCOME_STYLE.ya_estaba
                }`}
              >
                {OUTCOME_LABEL[step.outcome] ?? step.outcome}
              </span>
              <span className="text-vpv-text">{step.name}</span>
              <span className="text-xs text-vpv-text-muted">{step.detail}</span>
            </li>
          ))}
        </ul>

        {error && (
          <div className="mt-3 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400">
            {error}
          </div>
        )}

        {state.status !== "finished" && (
          <div className="mt-4 border-t border-vpv-card-border pt-4">
            {!allowed ? (
              <p className="text-xs text-vpv-text-muted">
                No se puede cerrar todavía: {state.blockers.join(" ")}
              </p>
            ) : confirming ? (
              <div className="space-y-2">
                <p className="text-sm text-vpv-text">
                  {movesMoney
                    ? "Esto generará los pagos semanales de la jornada. ¿Seguro?"
                    : "¿Cerrar la jornada?"}
                </p>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={handleClose}
                    disabled={closing}
                    className="rounded-md bg-vpv-accent px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
                  >
                    {closing ? "Cerrando…" : "Sí, cerrar"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirming(false)}
                    disabled={closing}
                    className="rounded-md border border-vpv-border px-3 py-1.5 text-sm font-medium text-vpv-text"
                  >
                    Cancelar
                  </button>
                </div>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setConfirming(true)}
                className="rounded-md bg-vpv-accent px-3 py-1.5 text-sm font-medium text-white"
              >
                Cerrar la jornada
              </button>
            )}
          </div>
        )}

        {result && (
          <div className="mt-4 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3">
            <p className="text-sm font-medium text-emerald-400">
              {result.closed ? "Jornada cerrada." : "No se cerró."}
            </p>
            <ul className="mt-1 space-y-0.5 text-xs text-vpv-text-muted">
              {result.steps.map((step) => (
                <li key={step.name}>
                  {OUTCOME_LABEL[step.outcome] ?? step.outcome} — {step.name}: {step.detail}
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>
    </div>
  );
}
