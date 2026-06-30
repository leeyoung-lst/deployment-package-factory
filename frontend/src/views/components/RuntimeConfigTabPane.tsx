import { Empty } from "antd";
import type { RuntimeConfigGroup, RuntimeResource } from "../../api/deploymentPackages";
import styles from "../DeploymentPackageExportView.module.css";
import { RuntimeGroupList } from "./RuntimeGroupList";
import { RuntimeResourceList } from "./RuntimeResourceList";

interface Props {
  label: string;
  tabKey: string;
  resources: RuntimeResource[];
  groups: RuntimeConfigGroup[];
  overrides: Record<string, string>;
  onChange: (name: string, value: string) => void;
}

export function RuntimeConfigTabPane({ label, tabKey, resources, groups, overrides, onChange }: Props) {
  if (!resources.length && !groups.length) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={`暂无${label}配置`} />;
  }
  return (
    <div className={styles.runtimeTabPane}>
      {resources.length ? (
        <section className={styles.runtimeTabSection}>
          <h3>初始化资源</h3>
          <RuntimeResourceList tabKey={tabKey} label={label} resources={resources} overrides={overrides} onChange={onChange} />
        </section>
      ) : null}
      {groups.length ? (
        <section className={styles.runtimeTabSection}>
          <h3>连接配置</h3>
          <RuntimeGroupList groups={groups} overrides={overrides} onChange={onChange} />
        </section>
      ) : null}
    </div>
  );
}
