"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";

const ADMIN_NAV = [
  {
    group: "Liga",
    items: [
      { href: "/admin/temporadas", label: "Temporadas" },
      { href: "/admin/jornadas", label: "Jornadas" },
      { href: "/admin/jugadores", label: "Jugadores" },
      { href: "/admin/estadisticas", label: "Estadisticas" },
    ],
  },
  {
    group: "Usuarios",
    items: [
      { href: "/admin/usuarios", label: "Usuarios" },
      { href: "/admin/invitaciones", label: "Invitaciones" },
      { href: "/admin/economia", label: "Economia" },
    ],
  },
  {
    group: "Operaciones",
    items: [
      { href: "/admin/scraping", label: "Scraping" },
      { href: "/admin/telegram", label: "Telegram" },
      { href: "/admin/backup", label: "Backup" },
    ],
  },
  {
    group: "Gestion",
    items: [
      { href: "/plantillas", label: "Plantillas" },
      { href: "/drafts/gestionar", label: "Drafts" },
    ],
  },
];

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-vpv-accent border-t-transparent" />
      </div>
    );
  }

  if (!user?.isAdmin) {
    router.push("/");
    return null;
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-vpv-text">Administracion</h1>

      <nav className="overflow-x-auto border-b border-vpv-border pb-px">
        <div className="flex items-center gap-1">
          {ADMIN_NAV.map((section, sIdx) => (
            <div key={section.group} className="flex items-center">
              {sIdx > 0 && (
                <div className="mx-1.5 h-4 w-px bg-vpv-border" />
              )}
              <span className="mr-1 hidden text-[10px] font-semibold uppercase tracking-wider text-vpv-text-muted/50 lg:inline">
                {section.group}
              </span>
              {section.items.map(({ href, label }) => {
                const active =
                  pathname === href || pathname.startsWith(href + "/");
                return (
                  <Link
                    key={href}
                    href={href}
                    className={`whitespace-nowrap rounded-t-md px-3 py-2 text-sm font-medium transition-colors ${
                      active
                        ? "border-b-2 border-vpv-accent text-vpv-accent"
                        : "text-vpv-text-muted hover:text-vpv-text"
                    }`}
                  >
                    {label}
                  </Link>
                );
              })}
            </div>
          ))}
        </div>
      </nav>

      {children}
    </div>
  );
}
