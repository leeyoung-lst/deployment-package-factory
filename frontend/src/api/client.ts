type RuntimeEnv = Record<string, string | undefined>;
interface RuntimeConfig {
  apiBaseUrl?: string;
  apiToken?: string;
}

declare global {
  interface Window {
    __DEPLOYMENT_PACKAGE_FACTORY_CONFIG__?: RuntimeConfig;
  }
}

function readRuntimeEnv(): RuntimeEnv {
  return (import.meta as ImportMeta & { env?: RuntimeEnv }).env ?? {};
}

function readRuntimeConfig(): RuntimeConfig {
  return window.__DEPLOYMENT_PACKAGE_FACTORY_CONFIG__ ?? {};
}

const runtimeConfig = readRuntimeConfig();
const buildEnv = readRuntimeEnv();

export const BASE = runtimeConfig.apiBaseUrl ?? buildEnv.VITE_API_BASE_URL ?? "";
const API_TOKEN = runtimeConfig.apiToken ?? buildEnv.VITE_DEPLOYMENT_PACKAGE_API_TOKEN ?? "";

export class ApiError extends Error {
  status: number;
  detail?: unknown;
  code?: string;

  constructor(message: string, status: number, detail?: unknown, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.code = code;
  }
}

export function authHeaders(): Record<string, string> {
  return API_TOKEN ? { Authorization: `Bearer ${API_TOKEN}` } : {};
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    cache: "no-store",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    throw await apiError(response);
  }
  return (await response.json()) as T;
}

export function buildDownloadUrl(path: string): string {
  const url = new URL(`${BASE}${path}`, window.location.origin);
  if (API_TOKEN) {
    url.searchParams.set("deployment_package_token", API_TOKEN);
  }
  return url.toString();
}

async function apiError(response: Response) {
  const text = await response.text();
  try {
    const payload = JSON.parse(text) as { detail?: unknown };
    if (typeof payload.detail === "string") return new ApiError(payload.detail, response.status, payload.detail);
    if (payload.detail && typeof payload.detail === "object" && "message" in payload.detail) {
      const detail = payload.detail as { code?: unknown; message?: unknown };
      return new ApiError(String(detail.message), response.status, payload.detail, typeof detail.code === "string" ? detail.code : undefined);
    }
    return new ApiError(text || response.statusText, response.status, payload.detail);
  } catch {
    return new ApiError(text || response.statusText, response.status);
  }
}
