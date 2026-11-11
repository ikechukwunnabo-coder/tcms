import type { LoginResponse, Paginated, StaffUser } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";
const TOKEN_KEY = "tcms.token";
const USER_KEY = "tcms.user";

export interface Session {
  token: string;
  user: StaffUser;
}

export const sessionStore = {
  load(): Session | null {
    const token = localStorage.getItem(TOKEN_KEY);
    const raw = localStorage.getItem(USER_KEY);
    if (!token || !raw) return null;
    try {
      return { token, user: JSON.parse(raw) as StaffUser };
    } catch {
      return null;
    }
  },
  save(session: Session) {
    localStorage.setItem(TOKEN_KEY, session.token);
    localStorage.setItem(USER_KEY, JSON.stringify(session.user));
  },
  clear() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },
};

export class ApiError extends Error {
  status: number;
  code: string;
  details: Record<string, string[]> | null;

  constructor(
    status: number,
    message: string,
    code = "error",
    details: Record<string, string[]> | null = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

type Query = Record<string, string | number | boolean | null | undefined>;

function url(path: string, params?: Query) {
  const root = path.startsWith("http") ? path : `${API_BASE}${path.startsWith("/") ? "" : "/"}${path}`;
  if (!params) return root;
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const query = search.toString();
  return query ? `${root}?${query}` : root;
}

async function parseError(response: Response): Promise<ApiError> {
  let body: {
    error?: string;
    message?: string;
    detail?: string;
    details?: Record<string, string[]>;
  } = {};
  try {
    body = await response.json();
  } catch {
    // A proxy error or HTML error page — keep the status-based fallback.
  }
  const message =
    body.message ??
    body.detail ??
    (response.status === 401
      ? "Your session has expired. Sign in again."
      : "The request could not be completed.");
  return new ApiError(response.status, message, body.error ?? "error", body.details ?? null);
}

export async function request<T>(
  path: string,
  options: RequestInit & { params?: Query } = {},
): Promise<T> {
  const { params, headers, ...rest } = options;
  const session = sessionStore.load();
  const isForm = rest.body instanceof FormData;
  const response = await fetch(url(path, params), {
    ...rest,
    headers: {
      Accept: "application/json",
      ...(rest.body && !isForm ? { "Content-Type": "application/json" } : {}),
      ...(session ? { Authorization: `Token ${session.token}` } : {}),
      ...headers,
    },
  });

  if (response.status === 401) {
    sessionStore.clear();
    window.dispatchEvent(new Event("tcms:unauthorized"));
    throw await parseError(response);
  }
  if (!response.ok) throw await parseError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function requestPublic<T>(path: string): Promise<T> {
  const response = await fetch(url(path), {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as T;
}

export function getList<T>(path: string, params?: Query) {
  return request<Paginated<T>>(path, { params });
}

export function login(identifier: string, password: string) {
  const value = identifier.trim();
  const payload = value.includes("@")
    ? { email: value, password }
    : { username: value, password };
  return request<LoginResponse>("auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function logout() {
  try {
    await request<void>("auth/logout", { method: "POST" });
  } finally {
    sessionStore.clear();
  }
}

export type ExportFormat = "csv" | "xlsx" | "pdf";

export async function downloadReport(
  dataset: string,
  format: ExportFormat = "csv",
  params?: Query,
) {
  const session = sessionStore.load();
  const response = await fetch(
    url("reports/export/", { dataset, format, ...params }),
    {
      headers: session ? { Authorization: `Token ${session.token}` } : {},
    },
  );
  if (!response.ok) throw await parseError(response);
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename="?([^"']+)"?/);
  const name = match?.[1] ?? `tcms-${dataset}.${format}`;
  const href = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = href;
  anchor.download = name;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(href);
}

export function downloadCsv(dataset: string, params?: Query) {
  return downloadReport(dataset, "csv", params);
}

export async function downloadFile(path: string, filename: string) {
  const session = sessionStore.load();
  const response = await fetch(url(path), {
    headers: session ? { Authorization: `Token ${session.token}` } : {},
  });
  if (!response.ok) throw await parseError(response);
  const blob = await response.blob();
  const href = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = href;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(href);
}

export async function downloadPaymentFile(id: number, filename: string) {
  const session = sessionStore.load();
  const response = await fetch(`${API_BASE}/payment-files/${id}/download/`, {
    headers: session ? { Authorization: `Token ${session.token}` } : {},
  });
  if (!response.ok) throw await parseError(response);
  const blob = await response.blob();
  const href = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = href;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(href);
}
