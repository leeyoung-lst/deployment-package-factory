import type { RuntimeConfigPreview } from "../../api/deploymentPackages";

export function runtimeConfigSnapshotOverrides(runtimeConfig: RuntimeConfigPreview | null, overrides: Record<string, string>) {
  const snapshot: Record<string, string> = {};
  for (const group of runtimeConfig?.groups ?? []) {
    for (const item of group.items) {
      if (item.editable === false) continue;
      const fieldName = item.overrideName || item.envName || item.name;
      snapshot[fieldName] = overrides[fieldName] ?? item.value ?? "";
    }
  }
  for (const resource of runtimeConfig?.resources ?? []) {
    for (const item of resource.items) {
      if (item.editable === false) continue;
      const fieldName = item.overrideName || item.envName || `${resource.key}.${item.name}`;
      snapshot[fieldName] = overrides[fieldName] ?? item.value ?? "";
    }
  }
  return { ...snapshot, ...overrides };
}
