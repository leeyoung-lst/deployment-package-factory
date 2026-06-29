import { request } from "./client";

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
    insecure: boolean;
  };
  jenkins: {
    baseUrl: string;
    folder: string;
    username: string;
  };
  updatedAt: string;
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
