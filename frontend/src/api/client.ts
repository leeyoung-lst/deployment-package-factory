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

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    cache: "no-store",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(API_TOKEN ? { Authorization: `Bearer ${API_TOKEN}` } : {}),
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
    return new Error(typeof payload.detail === "string" ? payload.detail : text || response.statusText);
  } catch {
    return new Error(text || response.statusText);
  }
}
