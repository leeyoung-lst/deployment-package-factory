import { BASE, authHeaders, request } from "./client";

export interface SystemSettings {
  git: {
    baseUrl: string;
    group: string;
    username: string;
    email: string;
  };
  harbor: {
    registry: string;
    project: string;
    username: string;
    password: string;
    insecure: boolean;
  };
  jenkins: {
    baseUrl: string;
    folder: string;
    username: string;
    password: string;
    deployJob: string;
    registryCredentialId: string;
    kubeconfigCredentialId: string;
  };
  kubernetes: {
    clusterName: string;
    ingressVip: string;
    factoryNamespace: string;
    defaultNamespace: string;
    kubeconfigPath: string;
    storageClass: string;
  };
  middleware: Record<string, MiddlewareEndpointSettings>;
  updatedAt: string;
}

export interface MiddlewareEndpointSettings {
  enabled: boolean;
  host: string;
  port?: number | null;
  username: string;
  password: string;
  database: string;
  namespace: string;
  notes: string;
}

export interface EnvironmentSettingsImportResult {
  settings: SystemSettings;
  importedFields: string[];
  warnings: string[];
}

export function getSystemSettings() {
  return request<SystemSettings>("/api/settings");
}

export function updateSystemSettings(payload: SystemSettings) {
  return request<SystemSettings>("/api/settings", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function importEnvironmentSettings(file: File) {
  const response = await fetch(`${BASE}/api/settings/import-environment`, {
    method: "POST",
    cache: "no-store",
    headers: { "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ...authHeaders() },
    body: await file.arrayBuffer(),
  });
  if (!response.ok) throw new Error(await response.text());
  return (await response.json()) as EnvironmentSettingsImportResult;
}
