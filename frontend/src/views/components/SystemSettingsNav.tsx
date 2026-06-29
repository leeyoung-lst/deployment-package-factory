import React from "react";
import { Button } from "antd";
import type { SettingsSection } from "../hooks/useSystemSettings";
import styles from "../SystemSettingsView.module.css";

const ITEMS: Array<{ key: SettingsSection; icon: string; title: string; desc: string }> = [
  { key: "git", icon: "ri-git-branch-line", title: "Git", desc: "仓库地址、默认分组、提交身份" },
  { key: "harbor", icon: "ri-archive-drawer-line", title: "Harbor", desc: "镜像仓库、项目、机器人账号" },
  { key: "jenkins", icon: "ri-flow-chart", title: "Jenkins", desc: "流水线地址、Job、凭据 ID" },
  { key: "kubernetes", icon: "ri-cloud-line", title: "K8s", desc: "集群入口、namespace、kubeconfig" },
  { key: "middleware", icon: "ri-database-2-line", title: "中间件", desc: "Redis、PostgreSQL、DM、MQ 等连接信息" },
];

export function SystemSettingsNav({ active, onChange }: { active: SettingsSection; onChange: (section: SettingsSection) => void }) {
  return (
    <aside className={styles.nav}>
      {ITEMS.map((item) => (
        <Button key={item.key} type={active === item.key ? "primary" : "text"} className={styles.navItem} onClick={() => onChange(item.key)}>
          <i className={item.icon} />
          <span>
            <strong>{item.title}</strong>
            <small>{item.desc}</small>
          </span>
        </Button>
      ))}
    </aside>
  );
}
