import { Input, Space, Tag } from "antd";
import type { RuntimeResource } from "../../api/deploymentPackages";
import styles from "../DeploymentPackageExportView.module.css";

interface Props {
  resource: RuntimeResource;
  overrides: Record<string, string>;
  onChange: (name: string, value: string) => void;
}

const sourceText: Record<string, string> = {
  "pod-env": "源环境识别",
  "source-secret": "源环境密钥",
  catalog: "待确认默认值",
  user: "人工修改",
};

export function RuntimeResourceEditor({ resource, overrides, onChange }: Props) {
  return (
    <div className={styles.runtimeResource}>
      <div className={styles.runtimeResourceHeader}>
        <div className={styles.runtimeResourceTitle}>
          <h3>{resource.name}</h3>
          <Space size={6} wrap>
            <Tag color={resource.shared ? "blue" : "default"}>{resource.shared ? "共用资源" : "独立资源"}</Tag>
            <Tag color={resource.source === "pod-env" ? "green" : "orange"}>{sourceText[resource.source] ?? resource.source}</Tag>
            {resource.needsReview ? <Tag color="warning">需确认</Tag> : null}
          </Space>
        </div>
        <div className={styles.runtimeUsedBy}>{resource.usedBy.map((item) => <Tag key={item}>{item}</Tag>)}</div>
      </div>
      <div className={styles.runtimeFields}>
        {resource.items.map((item) => {
          const fieldName = item.overrideName || item.envName || `${resource.key}.${item.name}`;
          const value = overrides[fieldName] ?? item.value ?? "";
          const editor = item.sensitive ? (
            <Input.Password autoComplete="new-password" value={value} onChange={(event) => onChange(fieldName, event.target.value)} />
          ) : (
            <Input value={value} onChange={(event) => onChange(fieldName, event.target.value)} />
          );
          return (
            <label key={fieldName} className={styles.runtimeField}>
              <span className={styles.runtimeFieldLabel}>{item.label}</span>
              {editor}
            </label>
          );
        })}
      </div>
    </div>
  );
}
