import { Input, Space, Tag } from "antd";
import type { RuntimeConfigGroup } from "../../api/deploymentPackages";
import styles from "../DeploymentPackageExportView.module.css";
import { runtimeSourceLabel } from "./runtimeConfigLabels";

interface Props {
  group: RuntimeConfigGroup;
  overrides: Record<string, string>;
  onChange: (name: string, value: string) => void;
}

export function RuntimeConfigGroupEditor({ group, overrides, onChange }: Props) {
  return (
    <div className={styles.runtimeResource}>
      <div className={styles.runtimeResourceHeader}>
        <div className={styles.runtimeResourceTitle}>
          <h3>{group.name}</h3>
          <Space size={6} wrap>
            <Tag>{group.key}</Tag>
            <Tag color={group.items.some((item) => !item.resolved) ? "warning" : "green"}>
              {group.items.some((item) => !item.resolved) ? "存在待确认项" : "已识别"}
            </Tag>
          </Space>
        </div>
      </div>
      <div className={styles.runtimeFields}>
        {group.items.map((item) => {
          const fieldName = item.overrideName || item.envName || item.name;
          const value = overrides[fieldName] ?? item.value ?? "";
          const source = runtimeSourceLabel({ ...item, value });
          const editor = item.sensitive ? (
            <Input.Password autoComplete="new-password" value={value} onChange={(event) => onChange(fieldName, event.target.value)} />
          ) : (
            <Input value={value} onChange={(event) => onChange(fieldName, event.target.value)} />
          );
          return (
            <label key={fieldName} className={styles.runtimeField}>
              <span className={styles.runtimeFieldLabel}>
                {item.label}
                <Tag color={source.color}>{source.text}</Tag>
              </span>
              {editor}
            </label>
          );
        })}
      </div>
    </div>
  );
}
