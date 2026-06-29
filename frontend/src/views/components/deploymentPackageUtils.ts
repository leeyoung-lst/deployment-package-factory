import type { DeploymentServiceOption, PackageTask, SourceEnv } from "../../api/deploymentPackages";

export type ExportDrawerKey = "preview" | "task" | "tasks" | "cleanup" | "audit";
export const DEFAULT_TARGET = {
  env: "prod",
  domain: "prod.example.com",
  sourceRegistry: "",
  sourceRegistryInsecure: false,
  registry: "",
  namespacePrefix: "prod",
  storageClass: "",
  exportImages: true,
};
export type TargetDraft = typeof DEFAULT_TARGET & { imageMode?: "image-manifest" | "image-archive" };
export const DEFAULT_IMAGE_MODE: TargetDraft["imageMode"] = "image-archive";
export const EXPORT_WIZARD_STEPS = ["产品范围", "平台能力", "中间件与镜像", "目标环境", "确认导出"];

export function taskStatusColor(status: PackageTask["status"]) {
  if (status === "completed") return "success";
  if (status === "failed") return "error";
  if (status === "canceled") return "default";
  if (status === "running") return "processing";
  return "default";
}

export function auditStatusColor(status: string) {
  if (status === "completed" || status === "accepted") return "success";
  if (status === "failed" || status === "error") return "error";
  if (status === "dry-run") return "blue";
  return "default";
}

export function exportDrawerTitle(key: ExportDrawerKey | null) {
  if (key === "preview") return "预览详情";
  if (key === "task") return "任务详情";
  if (key === "tasks") return "最近任务";
  if (key === "cleanup") return "产物清理";
  if (key === "audit") return "最近审计";
  return "";
}

export function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KiB`;
  if (value < 1024 * 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MiB`;
  return `${(value / 1024 / 1024 / 1024).toFixed(1)} GiB`;
}

export function triggerBrowserDownload(url: string, filename: string) {
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
}

export function mergeTaskIntoList(tasks: PackageTask[], task: PackageTask) {
  if (tasks.some((item) => item.taskId === task.taskId)) {
    return tasks.map((item) => (item.taskId === task.taskId ? task : item));
  }
  return [task, ...tasks].slice(0, 20);
}

export function businessOptionsForEnv(items: DeploymentServiceOption[], sourceEnv: SourceEnv) {
  return items.filter((item) => item.registered && item.sourceEnv === sourceEnv && item.status !== "disabled");
}

export function businessOptionValue(item: Pick<DeploymentServiceOption, "key" | "profile">) {
  return `${item.key}::${item.profile || ""}`;
}

export function businessPlatformRowKey(item: Pick<DeploymentServiceOption, "sourceEnv" | "key" | "profile">) {
  return `${item.sourceEnv}:${item.key}:${item.profile || ""}`;
}

export function parseBusinessOptionValue(value: string) {
  const [key, profile = ""] = value.split("::", 2);
  return { key, profile };
}

export function serviceOptionsForEnv<T extends { sourceEnv?: SourceEnv | "" }>(items: T[], sourceEnv: SourceEnv) {
  return items.filter((item) => item.sourceEnv === sourceEnv);
}
