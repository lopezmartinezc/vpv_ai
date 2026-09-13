"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { refreshAuthorisation } from "@/lib/auth-me";

interface AuthUser {
  id: string;
  username: string;
  displayName: string;
  isAdmin: boolean;
  permissions: number;
}

interface AuthContextValue {
  user: AuthUser | null;
  accessToken: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  accessToken: null,
  loading: true,
  login: async () => false,
  logout: () => {},
});

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

function parseJwt(token: string): Record<string, unknown> {
  const base64 = token.split(".")[1];
  const json = atob(base64);
  return JSON.parse(json);
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Restore session from localStorage on mount
  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect -- one-time hydration from localStorage */
    const stored = localStorage.getItem("vpv_token");
    if (stored) {
      try {
        const payload = parseJwt(stored);
        const exp = (payload.exp as number) * 1000;
        if (exp > Date.now()) {
          setAccessToken(stored);
          setUser({
            id: payload.sub as string,
            username: payload.username as string,
            displayName: payload.username as string,
            isAdmin: payload.is_admin as boolean,
            permissions: (payload.permissions as number) || 0,
          });
        } else {
          localStorage.removeItem("vpv_token");
        }
      } catch {
        localStorage.removeItem("vpv_token");
      }
    }
    setLoading(false);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, []);

  // Session heartbeat — validate session every 30s
  const heartbeatRef = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => {
    if (heartbeatRef.current) clearInterval(heartbeatRef.current);
    if (!accessToken) return;

    const check = async () => {
      try {
        const res = await fetch(`${API_URL}/auth/me`, {
          headers: { Authorization: `Bearer ${accessToken}` },
        });
        if (res.status === 401) {
          localStorage.removeItem("vpv_token");
          window.location.href = "/login";
          return;
        }
        if (res.ok) {
          // The token froze is_admin and permissions at login; the server knows
          // them now. Apply them, so a revoked permission leaves the menu too
          // instead of offering a screen that answers 403.
          const me = await res.json();
          setUser((current) => (current ? refreshAuthorisation(current, me) : current));
        }
      } catch {
        // Network error — skip
      }
    };

    // Once straight away, so a stale token does not show the wrong menu for the
    // first thirty seconds after a reload.
    void check();
    heartbeatRef.current = setInterval(check, 30_000);
    return () => {
      if (heartbeatRef.current) clearInterval(heartbeatRef.current);
    };
  }, [accessToken]);

  const login = useCallback(async (username: string, password: string) => {
    try {
      const res = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!res.ok) return false;

      const data = await res.json();
      const token = data.access_token as string;
      const payload = parseJwt(token);

      localStorage.setItem("vpv_token", token);
      setAccessToken(token);
      setUser({
        id: payload.sub as string,
        username: payload.username as string,
        displayName: payload.username as string,
        isAdmin: payload.is_admin as boolean,
        permissions: (payload.permissions as number) || 0,
      });
      return true;
    } catch {
      return false;
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("vpv_token");
    setAccessToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext value={{ user, accessToken, loading, login, logout }}>
      {children}
    </AuthContext>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
