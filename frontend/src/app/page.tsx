"use client";

import { useSeason } from "@/contexts/season-context";

export default function Home() {
  const { selectedSeason, loading } = useSeason();

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-vpv-text-muted">Cargando...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-6">
        <h1 className="text-2xl font-bold text-vpv-text">Liga VPV Fantasy</h1>
        {selectedSeason && (
          <p className="mt-1 text-vpv-text-muted">
            Temporada {selectedSeason.name} &mdash;{" "}
            {selectedSeason.total_participants} participantes
          </p>
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {[
          {
            title: "Clasificacion",
            href: "/clasificacion",
            desc: "Tabla general de la temporada",
          },
          {
            title: "Jornadas",
            href: "/jornadas",
            desc: "Puntuaciones por jornada",
          },
          {
            title: "Plantillas",
            href: "/plantillas",
            desc: "Equipos de cada participante",
          },
          {
            title: "Drafts",
            href: "/drafts",
            desc: "Historial de elecciones",
          },
          {
            title: "Economia",
            href: "/economia",
            desc: "Balance global de pagos",
          },
        ].map(({ title, href, desc }) => (
          <a
            key={href}
            href={href}
            className="rounded-lg border border-vpv-card-border bg-vpv-card p-4 transition-colors hover:border-vpv-accent"
          >
            <h2 className="font-semibold text-vpv-text">{title}</h2>
            <p className="mt-1 text-sm text-vpv-text-muted">{desc}</p>
          </a>
        ))}
      </div>
    </div>
  );
}
