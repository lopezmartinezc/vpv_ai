"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);

    const ok = await login(username, password);
    setSubmitting(false);

    if (ok) {
      router.push("/");
    } else {
      setError("Usuario o contrasena incorrectos");
    }
  }

  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <div className="w-full max-w-sm rounded-lg border border-vpv-card-border bg-vpv-card p-6">
        <h1 className="mb-6 text-center text-2xl font-bold text-vpv-text">
          Iniciar sesion
        </h1>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="username"
              className="mb-1 block text-sm font-medium text-vpv-text-muted"
            >
              Usuario
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoComplete="username"
              className="w-full rounded-md border border-vpv-border bg-vpv-bg px-3 py-2 text-vpv-text placeholder:text-vpv-text-muted focus:border-vpv-accent focus:outline-none focus:ring-1 focus:ring-vpv-accent"
              placeholder="Tu nombre de usuario"
            />
          </div>

          <div>
            <label
              htmlFor="password"
              className="mb-1 block text-sm font-medium text-vpv-text-muted"
            >
              Contrasena
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              className="w-full rounded-md border border-vpv-border bg-vpv-bg px-3 py-2 text-vpv-text placeholder:text-vpv-text-muted focus:border-vpv-accent focus:outline-none focus:ring-1 focus:ring-vpv-accent"
              placeholder="Tu contrasena"
            />
          </div>

          {error && (
            <p className="text-sm text-vpv-danger">{error}</p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-md bg-vpv-accent px-4 py-2 font-medium text-white transition-colors hover:bg-vpv-accent-hover disabled:opacity-50"
          >
            {submitting ? "Entrando..." : "Entrar"}
          </button>
        </form>
      </div>
    </div>
  );
}
