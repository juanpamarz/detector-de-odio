const BASE: string = (import.meta.env.VITE_API_URL as string | undefined) ?? "/api";
const TOKEN_KEY = "centinela-token";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type Primitive = string | number | boolean;
export type Params = Record<string, Primitive | Primitive[] | null | undefined>;

let token: string | null = readToken();
let onUnauthorized: (() => void) | null = null;

function readToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(value: string | null): void {
  token = value;
  try {
    if (value) sessionStorage.setItem(TOKEN_KEY, value);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    /* almacenamiento no disponible: el token vive solo en memoria */
  }
}

export const hasToken = (): boolean => token !== null;

export function setUnauthorizedHandler(handler: () => void): void {
  onUnauthorized = handler;
}

export function buildQuery(params?: Params): string {
  if (!params) return "";
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === "") continue;
    if (Array.isArray(value)) value.forEach((v) => qs.append(key, String(v)));
    else qs.append(key, String(value));
  }
  const s = qs.toString();
  return s ? `?${s}` : "";
}

async function request(path: string, init: RequestInit & { params?: Params } = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const res = await fetch(`${BASE}${path}${buildQuery(init.params)}`, { ...init, headers });
  if (res.status === 401 && token) {
    setToken(null);
    onUnauthorized?.();
  }
  if (!res.ok) {
    let detail = `Error ${res.status}`;
    try {
      const body: unknown = await res.json();
      if (body && typeof body === "object" && "detail" in body) {
        const d = (body as { detail: unknown }).detail;
        detail = typeof d === "string" ? d : "Revisa los datos enviados.";
      }
    } catch {
      /* cuerpo vacío */
    }
    throw new ApiError(res.status, detail);
  }
  return res;
}

export async function api<T>(path: string, init: RequestInit & { params?: Params } = {}): Promise<T> {
  const res = await request(path, init);
  return (await res.json()) as T;
}

export async function download(path: string, params: Params, fallbackName: string): Promise<void> {
  const res = await request(path, { params });
  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") ?? "";
  const name = /filename="([^"]+)"/.exec(disposition)?.[1] ?? fallbackName;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
