"use client";

import Link from "next/link";
import { useAuth } from "@/contexts/auth-context";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { Logo } from "@/components/ui/logo";

export function NavBar({ onMenuOpen }: { onMenuOpen: () => void }) {
  const { user, logout } = useAuth();

  return (
    <header className="sticky top-0 z-30 border-b border-vpv-border bg-vpv-card/95 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4">
        <button
          onClick={onMenuOpen}
          className="rounded-md p-2 text-vpv-text-muted transition-colors hover:text-vpv-text"
          aria-label="Abrir menu"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
            className="h-5 w-5"
          >
            <line x1={3} y1={6} x2={21} y2={6} />
            <line x1={3} y1={12} x2={21} y2={12} />
            <line x1={3} y1={18} x2={21} y2={18} />
          </svg>
        </button>

        <Link href="/" className="text-vpv-accent">
          <Logo className="h-10 w-auto" />
        </Link>

        <div className="ml-auto flex items-center gap-3">
          <ThemeToggle />
          {user ? (
            <div className="flex items-center gap-2">
              <span className="hidden text-sm text-vpv-text-muted sm:inline">
                {user.username}
              </span>
              <button
                onClick={logout}
                className="rounded-md px-3 py-1.5 text-sm font-medium text-vpv-text-muted transition-colors hover:text-vpv-text"
              >
                Salir
              </button>
            </div>
          ) : (
            <Link
              href="/login"
              className="rounded-md bg-vpv-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-vpv-accent-hover"
            >
              Entrar
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
