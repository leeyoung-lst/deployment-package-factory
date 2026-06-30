import { Empty } from "antd";
import type { RuntimeResource } from "../../api/deploymentPackages";
import styles from "../DeploymentPackageExportView.module.css";
import { RuntimeResourceEditor } from "./RuntimeResourceEditor";

interface Props {
  label: string;
  tabKey: string;
  resources: RuntimeResource[];
  overrides: Record<string, string>;
  onChange: (name: string, value: string) => void;
}

export function RuntimeResourceList({ label, tabKey, resources, overrides, onChange }: Props) {
  if (!resources.length) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={`暂无${label}配置`} />;
  }
  return (
    <div className={styles.runtimeConfigList}>
      {resources.map((resource) => (
        <RuntimeResourceEditor key={`${tabKey}-${resource.key}`} resource={resource} overrides={overrides} onChange={onChange} />
      ))}
    </div>
  );
}
