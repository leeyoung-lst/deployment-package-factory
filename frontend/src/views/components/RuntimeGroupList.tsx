import { Empty } from "antd";
import type { RuntimeConfigGroup } from "../../api/deploymentPackages";
import styles from "../DeploymentPackageExportView.module.css";
import { RuntimeConfigGroupEditor } from "./RuntimeConfigGroupEditor";

interface Props {
  groups: RuntimeConfigGroup[];
  overrides: Record<string, string>;
  onChange: (name: string, value: string) => void;
}

export function RuntimeGroupList({ groups, overrides, onChange }: Props) {
  if (!groups.length) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无中间件配置" />;
  }
  return (
    <div className={styles.runtimeConfigList}>
      {groups.map((group) => (
        <RuntimeConfigGroupEditor key={group.key} group={group} overrides={overrides} onChange={onChange} />
      ))}
    </div>
  );
}
