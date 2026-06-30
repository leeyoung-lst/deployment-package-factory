import React from "react";
import { Empty, Input, Space, Tag } from "antd";
import type { RuntimeConfigPreview, RuntimeResource } from "../../api/deploymentPackages";
import styles from "../DeploymentPackageExportView.module.css";

interface Props {
  runtimeConfig: RuntimeConfigPreview | null;
  overrides: Record<string, string>;
  onChange: (name: string, value: string) => void;
}

export function DeploymentRuntimeConfigStep(props: Props) {
  const resources = props.runtimeConfig?.resources ?? [];
  if (!resources.length) {
    return <div className={styles.wizardSection}><Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无运行配置，刷新预览后重试" /></div>;
  }
  return (
    <div className={styles.runtimeConfigLayout}>
      {resources.map((resource) => (
        <ResourceEditor key={resource.key} resource={resource} overrides={props.overrides} onChange={props.onChange} />
      ))}
    </div>
  );
}

function ResourceEditor({ resource, overrides, onChange }: { resource: RuntimeResource; overrides: Record<string, string>; onChange: (name: string, value: string) => void }) {
  return (
    <div className={styles.runtimeResource}>
      <div className={styles.runtimeResourceHeader}>
        <div>
          <h3>{resource.name}</h3>
          <Space size={6} wrap>
            <Tag color={resource.shared ? "blue" : "default"}>{resource.shared ? "共用资源" : "独立资源"}</Tag>
            <Tag color={resource.source === "pod-env" ? "green" : "orange"}>{resource.source === "pod-env" ? "源环境识别" : "待确认默认值"}</Tag>
            {resource.needsReview ? <Tag color="warning">需确认</Tag> : null}
          </Space>
        </div>
        <div className={styles.runtimeUsedBy}>{resource.usedBy.map((item) => <Tag key={item}>{item}</Tag>)}</div>
      </div>
      <div className={styles.runtimeFields}>
        {resource.items.slice(0, 4).map((item) => {
          const fieldName = item.overrideName || item.envName || `${resource.key}.${item.name}`;
          const value = overrides[fieldName] ?? item.value ?? "";
          const editor = item.sensitive ? (
            <Input.Password autoComplete="new-password" value={value} onChange={(event) => onChange(fieldName, event.target.value)} />
          ) : (
            <Input value={value} onChange={(event) => onChange(fieldName, event.target.value)} />
          );
          return (
            <label key={fieldName} className={styles.runtimeField}>
              <span>{item.label}</span>
              {editor}
            </label>
          );
        })}
      </div>
    </div>
  );
}
