"use client";

import Link from "next/link";
import { useAuth } from "@/contexts/auth-context";
import { useSeason } from "@/contexts/season-context";
import { MatchdayCenterPanel } from "@/features/matchday-center/panel";
import {
  ADMIN_ITEMS,
  canSeeAdminItem,
  hrefForSeason,
} from "@/lib/admin-nav";
import { PERM, userHasPerm } from "@/lib/permissions";

/**
 * The way into admin.
 *
 * It used to be `redirect("/admin/usuarios")`, and Usuarios is super-admin only:
 * a delegate with, say, only MATCHDAYS landed on a screen he could not open. So
 * the entrance depended on being the one person who never needed an entrance.
 *
 * Now it answers "what needs attention" for whoever is asking — the jornada for
 * anyone who can work on matchdays, and otherwise what they can actually reach.
 */
export default function AdminPage() {
  const { user } = useAuth();
  const { selectedSeason, loading } = useSeason();

  if (!user || loading) {
    return (
      <div className="flex min-h-[30vh] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-vpv-accent border-t-transparent" />
      </div>
    );
  }

  const canSeeMatchdays = userHasPerm(user.isAdmin, user.permissions, PERM.MATCHDAYS);
  const reachable = ADMIN_ITEMS.filter((item) =>
    canSeeAdminItem(user.isAdmin, user.permissions, item),
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-vpv-text">Qué necesita atención</h1>
        {selectedSeason && (
          <p className="text-sm text-vpv-text-muted">{selectedSeason.name}</p>
        )}
      </div>

      {canSeeMatchdays && selectedSeason ? (
        <MatchdayCenterPanel
          seasonId={selectedSeason.id}
          matchdayNumber={selectedSeason.matchday_current}
        />
      ) : (
        <section className="rounded-lg border border-vpv-card-border bg-vpv-card p-5">
          <h2 className="mb-1 text-sm font-semibold text-vpv-text">Tus herramientas</h2>
          <p className="mb-3 text-xs text-vpv-text-muted">
            Lo que puedes gestionar con tus permisos.
          </p>
          {reachable.length === 0 ? (
            <p className="text-sm text-vpv-text-muted">
              No tienes ninguna sección asignada. Pídele permisos a un administrador.
            </p>
          ) : (
            <ul className="grid gap-2 sm:grid-cols-2">
              {reachable.map((item) => (
                <li key={item.href}>
                  <Link
                    href={hrefForSeason(item, selectedSeason?.id)}
                    className="block rounded-md border border-vpv-card-border bg-vpv-bg px-3 py-2 text-sm font-medium text-vpv-text transition-colors hover:border-vpv-border"
                  >
                    {item.label}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
