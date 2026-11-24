/**
 * Typed API client.
 *
 * - Uses relative URLs so the Next.js server can proxy to the backend (works in
 *   remote previews where the browser cannot reach localhost).
 * - Retries once with the refresh token on 401.
 * - Normalises backend error envelopes into readable Error messages.
 */

const BASE = process.env.NEXT_PUBLIC_API_BASE || "/api/v1";
const TOKEN_KEY = "sw_access_token";
const REFRESH_KEY = "sw_refresh_token";

export class ApiError extends Error {
  status: number;
  code?: string;
  details?: unknown;

  constructor(message: string, status: number, code?: string, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export const tokenStore = {
  get: () => ({
    access: typeof window !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null,
    refresh: typeof window !== "undefined" ? localStorage.getItem(REFRESH_KEY) : null,
  }),
  set: (access: string, refresh: string) => {
    if (typeof window === "undefined") return;
    localStorage.setItem(TOKEN_KEY, access);
    localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear: () => {
    if (typeof window === "undefined") return;
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

let refreshing: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  const refresh = tokenStore.get().refresh;
  if (!refresh) return false;
  try {
    const response = await fetch(`${BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!response.ok) return false;
    const data = await response.json();
    tokenStore.set(data.access_token, data.refresh_token);
    return true;
  } catch {
    return false;
  }
}

type RequestOptions = Omit<RequestInit, "body"> & { body?: unknown; params?: Record<string, unknown> };

function buildUrl(path: string, params?: Record<string, unknown>) {
  const url = `${BASE}${path.startsWith("/") ? path : `/${path}`}`;
  if (!params) return url;
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  });
  const query = search.toString();
  return query ? `${url}?${query}` : url;
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}, retry = true): Promise<T> {
  const { body, params, headers, ...rest } = options;
  const token = tokenStore.get().access;
  const init: RequestInit = {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(headers || {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  };

  let response: Response;
  try {
    response = await fetch(buildUrl(path, params), init);
  } catch {
    throw new ApiError("Cannot reach the SafeWay API. Check that the backend is running.", 0);
  }

  if (response.status === 401 && retry) {
    if (!refreshing) {
      refreshing = tryRefresh().finally(() => {
        refreshing = null;
      });
    }
    const refreshed = await refreshing;
    if (refreshed) return apiFetch<T>(path, options, false);
    tokenStore.clear();
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
  }

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    let code: string | undefined;
    let details: unknown;
    try {
      const payload = await response.json();
      message = payload?.error?.message || payload?.detail || message;
      code = payload?.error?.code;
      details = payload?.error?.details;
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(message, response.status, code, details);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string, params?: Record<string, unknown>) => apiFetch<T>(path, { params }),
  post: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, { method: "POST", body: body ?? {} }),
  patch: <T>(path: string, body?: unknown) => apiFetch<T>(path, { method: "PATCH", body }),
  put: <T>(path: string, body?: unknown) => apiFetch<T>(path, { method: "PUT", body }),
  delete: <T>(path: string) => apiFetch<T>(path, { method: "DELETE" }),
};

export type Paginated<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};
