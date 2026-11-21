export type Role = "admin" | "tpo" | "coordinator" | "student" | "employer";
export interface User {
  id: number;
  email: string;
  name: string;
  role: Role;
  institute_id: number | null;
  employer_id: number | null;
}

const TOKEN_KEY = "srk_token";
const USER_KEY = "srk_user";

function read(key: string): string | null {
  try {
    return sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

export function savedUser(): User | null {
  const raw = read(USER_KEY);
  return raw ? (JSON.parse(raw) as User) : null;
}

export function saveSession(token: string, user: User) {
  try {
    sessionStorage.setItem(TOKEN_KEY, token);
    sessionStorage.setItem(USER_KEY, JSON.stringify(user));
  } catch {
    /* storage unavailable: session lasts for this page only */
  }
  memToken = token;
}

export function clearSession() {
  memToken = null;
  try {
    sessionStorage.clear();
  } catch {
    /* ignore */
  }
}

let memToken: string | null = read(TOKEN_KEY);

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function api<T = any>(path: string, opts: RequestInit & { json?: unknown } = {}): Promise<T> {
  const headers: Record<string, string> = { ...(opts.headers as Record<string, string>) };
  if (memToken) headers.Authorization = `Bearer ${memToken}`;
  let body = opts.body;
  if (opts.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.json);
  }
  const res = await fetch(path, { ...opts, headers, body });
  if (res.status === 401 && !path.endsWith("/login")) {
    clearSession();
    window.location.href = "/";
  }
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const j = await res.json();
      msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* not json */
    }
    throw new ApiError(res.status, msg);
  }
  const ct = res.headers.get("content-type") || "";
  return (ct.includes("json") ? res.json() : res.text()) as Promise<T>;
}

export async function download(path: string, filename: string) {
  const res = await fetch(path, { headers: memToken ? { Authorization: `Bearer ${memToken}` } : {} });
  if (!res.ok) throw new ApiError(res.status, "Download failed");
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}
