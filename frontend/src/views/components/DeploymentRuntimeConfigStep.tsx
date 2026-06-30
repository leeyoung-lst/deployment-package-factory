import { Empty, Tabs } from "antd";
import type { RuntimeConfigGroup, RuntimeConfigPreview, RuntimeResource } from "../../api/deploymentPackages";
import styles from "../DeploymentPackageExportView.module.css";
import { RuntimeConfigTabPane } from "./RuntimeConfigTabPane";

interface Props {
  runtimeConfig: RuntimeConfigPreview | null;
  overrides: Record<string, string>;
  onChange: (name: string, value: string) => void;
}

type ResourceTab = {
  key: string;
  label: string;
  resources: RuntimeResource[];
  groups?: RuntimeConfigGroup[];
};

export function DeploymentRuntimeConfigStep(props: Props) {
  const resources = props.runtimeConfig?.resources ?? [];
  const groups = props.runtimeConfig?.groups ?? [];
  if (!resources.length && !groups.length) {
    return <div className={styles.wizardSection}><Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无运行配置，刷新预览后重试" /></div>;
  }
  const resourceTabs = runtimeResourceTabs(resources, groups);
  return (
    <Tabs
      className={styles.runtimeConfigTabs}
      items={[
        ...resourceTabs.map((tab) => ({
          key: tab.key,
          label: `${tab.label} ${tab.resources.length + (tab.groups?.length ?? 0)}`,
          children: (
            <RuntimeConfigTabPane
              tabKey={tab.key}
              label={tab.label}
              resources={tab.resources}
              groups={tab.groups ?? []}
              overrides={props.overrides}
              onChange={props.onChange}
            />
          ),
        })),
      ]}
    />
  );
}

function runtimeResourceTabs(resources: RuntimeResource[], groups: RuntimeConfigGroup[]): ResourceTab[] {
  const unresolved = resources.filter((resource) => resource.needsReview || resource.items.some((item) => !item.resolved));
  const unresolvedGroups = groups.filter((group) => group.items.some((item) => !item.resolved));
  const categorized = new Set(["postgres", "dm", "minio", "redis", "iotdb", "qdrant"]);
  return [
    { key: "review", label: "待确认", resources: unresolved, groups: unresolvedGroups },
    {
      key: "database",
      label: "数据库",
      resources: resources.filter((resource) => resource.type === "databaseSchema"),
      groups: groups.filter((group) => ["postgres", "dm"].includes(group.key)),
    },
    {
      key: "object-storage",
      label: "对象存储",
      resources: resources.filter((resource) => resource.type === "bucket"),
      groups: groups.filter((group) => group.key === "minio"),
    },
    {
      key: "cache",
      label: "缓存 Redis",
      resources: [],
      groups: groups.filter((group) => group.key === "redis"),
    },
    {
      key: "timeseries",
      label: "时序 IoTDB",
      resources: [],
      groups: groups.filter((group) => group.key === "iotdb"),
    },
    {
      key: "vector",
      label: "向量库",
      resources: resources.filter((resource) => resource.type === "collection" || resource.middlewareKey === "qdrant"),
      groups: groups.filter((group) => group.key === "qdrant"),
    },
    {
      key: "middleware-other",
      label: "其他中间件",
      resources: [],
      groups: groups.filter((group) => !categorized.has(group.key)),
    },
  ];
}
