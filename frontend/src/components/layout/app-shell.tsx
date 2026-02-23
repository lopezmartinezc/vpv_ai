"use client";

import { SeasonProvider } from "@/contexts/season-context";
import { NavBar } from "./nav-bar";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <SeasonProvider>
      <div className="min-h-screen bg-vpv-bg">
        <NavBar />
        <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
      </div>
    </SeasonProvider>
  );
}
