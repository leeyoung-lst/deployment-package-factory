import type { RuntimeConfigItem } from "../../api/deploymentPackages";

const sourceText: Record<string, string> = {
  "pod-env": "源环境识别",
  "source-secret": "源环境密钥",
  catalog: "模板默认值",
  user: "人工修改",
};

export function runtimeSourceLabel(item: Pick<RuntimeConfigItem, "source" | "resolved" | "value">) {
  const value = String(item.value || "");
  if (!value.trim() || value.includes("__REPLACE_WITH_")) {
    return { text: "待确认占位符", color: "warning" };
  }
  return {
    text: sourceText[item.source] ?? item.source,
    color: item.source === "pod-env" || item.source === "source-secret" ? "green" : "orange",
  };
}
