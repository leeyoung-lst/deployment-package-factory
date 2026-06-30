import type { RuntimeConfigItem, RuntimeResource } from "../../api/deploymentPackages";

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

const middlewareText: Record<string, string> = {
  postgres: "PostgreSQL",
  dm: "达梦",
  minio: "MinIO",
  qdrant: "Qdrant",
};

const resourceTypeText: Record<string, string> = {
  databaseSchema: "数据库",
  bucket: "对象存储",
  collection: "向量库",
};

const resourceColor: Record<string, string> = {
  databaseSchema: "geekblue",
  bucket: "cyan",
  collection: "purple",
};

export function runtimeResourceLabel(resource: Pick<RuntimeResource, "type" | "middlewareKey">) {
  const type = resourceTypeText[resource.type] ?? resource.type;
  const middleware = middlewareText[resource.middlewareKey] ?? resource.middlewareKey;
  return {
    text: middleware ? `${type} / ${middleware}` : type,
    color: resourceColor[resource.type] ?? "default",
  };
}
