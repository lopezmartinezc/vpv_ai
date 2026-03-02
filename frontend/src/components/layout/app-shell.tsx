"use client";

import { useState } from "react";
import { AuthProvider } from "@/contexts/auth-context";
import { ThemeProvider } from "@/contexts/theme-context";
import { SeasonProvider } from "@/contexts/season-context";
import { NavBar } from "./nav-bar";
import { Sidebar } from "./sidebar";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <AuthProvider>
      <ThemeProvider>
        <SeasonProvider>
          <div className="min-h-screen bg-vpv-bg">
            <NavBar onMenuOpen={() => setSidebarOpen(true)} />
            <Sidebar
              open={sidebarOpen}
              onClose={() => setSidebarOpen(false)}
            />
            <main className="mx-auto max-w-7xl px-4 py-6">
              {children}
            </main>
          </div>
        </SeasonProvider>
      </ThemeProvider>
    </AuthProvider>
  );
}
