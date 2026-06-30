import { Input, Space, Tag } from "antd";
import type { RuntimeResource } from "../../api/deploymentPackages";
import styles from "../DeploymentPackageExportView.module.css";
import { runtimeSourceLabel } from "./runtimeConfigLabels";

interface Props {
  resource: RuntimeResource;
  overrides: Record<string, string>;
  onChange: (name: string, value: string) => void;
}

export function RuntimeResourceEditor({ resource, overrides, onChange }: Props) {
  const values = resource.items.map((item) => runtimeItemValue(resource, item, overrides));
  const hasUnresolved = resource.needsReview || values.some((value) => !value.trim() || value.includes("__REPLACE_WITH_"));
  const source = runtimeSourceLabel({ source: resource.source, resolved: !hasUnresolved, value: hasUnresolved ? "" : resource.name });
  return (
    <div className={styles.runtimeResource}>
      <div className={styles.runtimeResourceHeader}>
        <div className={styles.runtimeResourceTitle}>
          <h3>{resource.name}</h3>
          <Space size={6} wrap>
            <Tag color={resource.shared ? "blue" : "default"}>{resource.shared ? "共用资源" : "独立资源"}</Tag>
            <Tag color={source.color}>{source.text}</Tag>
            {resource.needsReview ? <Tag color="warning">需确认</Tag> : null}
          </Space>
        </div>
        <div className={styles.runtimeUsedBy}>{resource.usedBy.map((item) => <Tag key={item}>{item}</Tag>)}</div>
      </div>
      <div className={styles.runtimeFields}>
        {resource.items.map((item) => {
          const fieldName = item.overrideName || item.envName || `${resource.key}.${item.name}`;
          const value = runtimeItemValue(resource, item, overrides);
          const itemSource = runtimeSourceLabel({ ...item, value });
          const editor = item.sensitive ? (
            <Input.Password autoComplete="new-password" value={value} onChange={(event) => onChange(fieldName, event.target.value)} />
          ) : (
            <Input value={value} onChange={(event) => onChange(fieldName, event.target.value)} />
          );
          return (
            <label key={fieldName} className={styles.runtimeField}>
              <span className={styles.runtimeFieldLabel}>
                {item.label}
                <Tag color={itemSource.color}>{itemSource.text}</Tag>
              </span>
              {editor}
            </label>
          );
        })}
      </div>
    </div>
  );
}

function runtimeItemValue(resource: RuntimeResource, item: RuntimeResource["items"][number], overrides: Record<string, string>) {
  const fieldName = item.overrideName || item.envName || `${resource.key}.${item.name}`;
  return overrides[fieldName] ?? item.value ?? "";
}
