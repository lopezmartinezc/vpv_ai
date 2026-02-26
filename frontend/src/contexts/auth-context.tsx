"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

interface AuthUser {
  id: string;
  username: string;
  displayName: string;
  isAdmin: boolean;
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
          });
        } else {
          localStorage.removeItem("vpv_token");
        }
      } catch {
        localStorage.removeItem("vpv_token");
      }
    }
    setLoading(false);
  }, []);

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
