"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, tokenStore } from "@/lib/api";
import type { AuthMe, Organisation, Subscription, Usage, User } from "@/lib/types";

interface LoginResult {
  access_token: string;
  refresh_token: string;
  user: User;
}

interface AuthContextValue {
  user: User | null;
  organisation: Organisation | null;
  subscription: Subscription | null;
  usage: Usage | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (payload: Record<string, unknown>) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
  hasPermission: (permission: string) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [organisation, setOrganisation] = useState<Organisation | null>(null);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [loading, setLoading] = useState(true);

  const applyMe = useCallback((me: AuthMe) => {
    setUser(me.user);
    setOrganisation(me.organisation ?? null);
    setSubscription(me.subscription ?? null);
    setUsage(me.usage ?? null);
  }, []);

  const refresh = useCallback(async () => {
    const token = tokenStore.get().access;
    if (!token) {
      setLoading(false);
      return;
    }
    try {
      const me = await api.get<AuthMe>("/auth/me");
      applyMe(me);
    } catch {
      tokenStore.clear();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, [applyMe]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const login = useCallback(
    async (email: string, password: string) => {
      const result = await api.post<LoginResult>("/auth/login", { email, password });
      tokenStore.set(result.access_token, result.refresh_token);
      const me = await api.get<AuthMe>("/auth/me");
      applyMe(me);
    },
    [applyMe],
  );

  const register = useCallback(
    async (payload: Record<string, unknown>) => {
      const result = await api.post<{ token: LoginResult }>("/auth/register", payload);
      tokenStore.set(result.token.access_token, result.token.refresh_token);
      const me = await api.get<AuthMe>("/auth/me");
      applyMe(me);
    },
    [applyMe],
  );

  const logout = useCallback(() => {
    const refresh_token = tokenStore.get().refresh;
    tokenStore.clear();
    setUser(null);
    setOrganisation(null);
    setSubscription(null);
    setUsage(null);
    if (refresh_token) {
      api.post("/auth/logout", { refresh_token }).catch(() => undefined);
    }
    window.location.href = "/login";
  }, []);

  const hasPermission = useCallback(
    (permission: string) => {
      if (!user) return false;
      if (user.role === "super_admin") return true;
      return user.permissions.includes(permission) || user.permissions.includes(`${permission.split(":")[0]}:*`);
    },
    [user],
  );

  const value = useMemo(
    () => ({
      user,
      organisation,
      subscription,
      usage,
      loading,
      isAuthenticated: Boolean(user),
      login,
      register,
      logout,
      refresh,
      hasPermission,
    }),
    [user, organisation, subscription, usage, loading, login, register, logout, refresh, hasPermission],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
