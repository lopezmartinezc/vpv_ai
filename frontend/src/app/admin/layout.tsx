"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";

const ADMIN_TABS = [
  { href: "/admin/usuarios", label: "Usuarios" },
  { href: "/admin/invitaciones", label: "Invitaciones" },
  { href: "/admin/scraping", label: "Scraping" },
  { href: "/admin/temporadas", label: "Temporadas" },
  { href: "/admin/jornadas", label: "Jornadas" },
  { href: "/admin/economia", label: "Economia" },
  { href: "/admin/telegram", label: "Telegram" },
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

      <nav className="flex gap-1 overflow-x-auto border-b border-vpv-border pb-px">
        {ADMIN_TABS.map(({ href, label }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
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
      </nav>

      {children}
    </div>
  );
}
