import type { DeploymentServiceOption } from "../../api/deploymentPackages";

export const K8S_NAME_PATTERN = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/;
export const IMAGE_PATH_PATTERN = /^[a-z0-9]+(?:[._-][a-z0-9]+)*(?:\/[a-z0-9]+(?:[._-][a-z0-9]+)*)*$/;
export const REGISTRY_HOST_PATTERN = /^[^\s/]+$/;

export function businessPlatformValue(item: DeploymentServiceOption) {
  return `${item.key}::${item.profile || ""}`;
}

export function parseBusinessPlatformValue(value: string) {
  const [key, profile = ""] = value.split("::", 2);
  return { key, profile };
}

export function normalizeK8sName(value: string) {
  return (value || "").trim().toLowerCase();
}

export function normalizePathValue(value: string) {
  return (value || "").trim().toLowerCase().replace(/^\/+|\/+$/g, "");
}

export function normalizeRegistry(value: string) {
  return (value || "").trim().replace(/\/+$/g, "");
}

export function parseApiErrorDetails(error: unknown): Array<{ loc: string[]; msg: string }> {
  if (!(error instanceof Error)) return [];
  try {
    const payload = JSON.parse(error.message) as { detail?: Array<{ loc?: unknown[]; msg?: string }> };
    return (payload.detail ?? []).map((item) => ({
      loc: (item.loc ?? []).filter((part): part is string => typeof part === "string"),
      msg: item.msg ?? "",
    }));
  } catch {
    return [];
  }
}
