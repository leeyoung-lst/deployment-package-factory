type RuntimeEnv = Record<string, string | undefined>;

function readRuntimeEnv(): RuntimeEnv {
  return (import.meta as ImportMeta & { env?: RuntimeEnv }).env ?? {};
}

export const BASE = readRuntimeEnv().VITE_API_BASE_URL ?? "";

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    cache: "no-store",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    throw await apiError(response);
  }
  return (await response.json()) as T;
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
