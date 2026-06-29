import React from "react";
import { Button, Empty, Popconfirm, Space, Tag } from "antd";
import type { DeploymentPackageOptions, DeploymentServiceOption } from "../../api/deploymentPackages";
import { businessPlatformRowKey } from "./deploymentPackageUtils";
import styles from "../DeploymentPackageExportView.module.css";

interface Props {
  disablingBusinessKey: string;
  loading: boolean;
  options: DeploymentPackageOptions | null;
  registeredBusinessOptions: DeploymentServiceOption[];
  onDisable: (item: DeploymentServiceOption) => void;
  onRefresh: () => void;
  onRegister: () => void;
}

export function PlatformRegistryPanel({ disablingBusinessKey, loading, registeredBusinessOptions, onDisable, onRefresh, onRegister }: Props) {
  return (
    <div className={styles.registryLayout}>
      <div className={styles.resultPanel}>
        <div className={styles.panelTitleRow}>
          <div>
            <h3 className={styles.sectionTitle}>业务平台 namespace</h3>
            <span className={styles.muted}>业务平台按环境注册，一个环境下的业务平台对应一个 namespace。</span>
          </div>
          <Space>
            <Button icon={<i className="ri-refresh-line" />} loading={loading} onClick={onRefresh}>刷新</Button>
            <Button type="primary" icon={<i className="ri-add-circle-line" />} onClick={onRegister}>注册业务平台</Button>
          </Space>
        </div>
        {registeredBusinessOptions.length ? <PlatformList items={registeredBusinessOptions} disablingBusinessKey={disablingBusinessKey} onDisable={onDisable} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无已注册业务平台" />}
      </div>
    </div>
  );
}

function PlatformList({ items, disablingBusinessKey, onDisable }: { items: DeploymentServiceOption[]; disablingBusinessKey: string; onDisable: (item: DeploymentServiceOption) => void }) {
  return (
    <div className={styles.taskList}>
      {items.map((item) => (
        <div key={`${item.sourceEnv}-${item.key}-${item.namespace}`} className={styles.taskItem}>
          <span className={styles.taskItemMain}>
            <span><strong>{item.name}</strong><Tag color="blue" style={{ marginLeft: 8 }}>{item.sourceEnv}</Tag><Tag color="green">{item.status || "active"}</Tag></span>
            <span className={styles.mono}>{item.namespace}</span>
          </span>
          <Popconfirm title="注销业务平台？" description="注销只会标记 namespace 停用，不会物理删除业务资源。" onConfirm={() => onDisable(item)}>
            <Button danger size="small" icon={<i className="ri-forbid-line" />} loading={disablingBusinessKey === businessPlatformRowKey(item)}>注销</Button>
          </Popconfirm>
        </div>
      ))}
    </div>
  );
}
