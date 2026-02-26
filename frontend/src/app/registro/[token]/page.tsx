"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

interface InviteStatus {
  valid: boolean;
  target_user_id: number | null;
  target_display_name: string | null;
  expired: boolean;
}

export default function RegistroPage() {
  const { token } = useParams<{ token: string }>();
  const router = useRouter();
  const { login } = useAuth();

  const [invite, setInvite] = useState<InviteStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!token) return;
    fetch(`${API_URL}/auth/invite/${token}`)
      .then((r) => r.json())
      .then((data: InviteStatus) => setInvite(data))
      .catch(() => setInvite({ valid: false, target_user_id: null, target_display_name: null, expired: true }))
      .finally(() => setLoading(false));
  }, [token]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    if (password.length < 8) {
      setError("La contrasena debe tener al menos 8 caracteres");
      return;
    }
    if (password !== passwordConfirm) {
      setError("Las contrasenas no coinciden");
      return;
    }
    if (!invite?.target_user_id && !username.trim()) {
      setError("El nombre de usuario es obligatorio");
      return;
    }

    setSubmitting(true);

    try {
      const res = await fetch(`${API_URL}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token,
          username: invite?.target_user_id ? undefined : username,
          password,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        setError(data?.message || "Error al registrar");
        setSubmitting(false);
        return;
      }

      // Auto-login after registration
      const loginUsername = invite?.target_user_id
        ? invite.target_display_name || ""
        : username;
      const ok = await login(loginUsername, password);

      if (ok) {
        router.push("/");
      } else {
        router.push("/login");
      }
    } catch {
      setError("Error de conexion");
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-vpv-accent border-t-transparent" />
      </div>
    );
  }

  if (!invite?.valid) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="w-full max-w-sm rounded-lg border border-vpv-card-border bg-vpv-card p-6 text-center">
          <h1 className="mb-2 text-xl font-bold text-vpv-danger">
            Invitacion no valida
          </h1>
          <p className="text-sm text-vpv-text-muted">
            {invite?.expired
              ? "Esta invitacion ha expirado o ya fue utilizada."
              : "El enlace de invitacion no es valido."}
          </p>
        </div>
      </div>
    );
  }

  const isExistingUser = !!invite.target_user_id;

  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <div className="w-full max-w-sm rounded-lg border border-vpv-card-border bg-vpv-card p-6">
        <h1 className="mb-2 text-center text-2xl font-bold text-vpv-text">
          {isExistingUser ? "Establecer contrasena" : "Registro"}
        </h1>
        {isExistingUser && (
          <p className="mb-4 text-center text-sm text-vpv-text-muted">
            Bienvenido, <span className="font-medium text-vpv-accent">{invite.target_display_name}</span>
          </p>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {!isExistingUser && (
            <div>
              <label
                htmlFor="username"
                className="mb-1 block text-sm font-medium text-vpv-text-muted"
              >
                Nombre de usuario
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoComplete="username"
                className="w-full rounded-md border border-vpv-border bg-vpv-bg px-3 py-2 text-vpv-text placeholder:text-vpv-text-muted focus:border-vpv-accent focus:outline-none focus:ring-1 focus:ring-vpv-accent"
              />
            </div>
          )}

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
              minLength={8}
              autoComplete="new-password"
              className="w-full rounded-md border border-vpv-border bg-vpv-bg px-3 py-2 text-vpv-text placeholder:text-vpv-text-muted focus:border-vpv-accent focus:outline-none focus:ring-1 focus:ring-vpv-accent"
              placeholder="Minimo 8 caracteres"
            />
          </div>

          <div>
            <label
              htmlFor="passwordConfirm"
              className="mb-1 block text-sm font-medium text-vpv-text-muted"
            >
              Confirmar contrasena
            </label>
            <input
              id="passwordConfirm"
              type="password"
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
              required
              autoComplete="new-password"
              className="w-full rounded-md border border-vpv-border bg-vpv-bg px-3 py-2 text-vpv-text placeholder:text-vpv-text-muted focus:border-vpv-accent focus:outline-none focus:ring-1 focus:ring-vpv-accent"
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
            {submitting ? "Registrando..." : isExistingUser ? "Establecer contrasena" : "Registrarse"}
          </button>
        </form>
      </div>
    </div>
  );
}
