"use client";

import { ThemeProvider } from "@/contexts/theme-context";
import { SeasonProvider } from "@/contexts/season-context";
import { NavBar } from "./nav-bar";
import { BottomNav } from "./bottom-nav";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <SeasonProvider>
        <div className="min-h-screen bg-vpv-bg">
          <NavBar />
          <main className="mx-auto max-w-7xl px-4 py-6 pb-20 md:pb-6">
            {children}
          </main>
          <BottomNav />
        </div>
      </SeasonProvider>
    </ThemeProvider>
  );
}
