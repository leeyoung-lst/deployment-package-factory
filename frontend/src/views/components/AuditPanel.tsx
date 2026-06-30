import { useMemo, useState } from "react";
import { Button, Empty, Segmented, Space, Tag } from "antd";
import type { AuditEvent } from "../../api/deploymentPackages";
import { auditActionLabel, auditStatusColor } from "./deploymentPackageUtils";
import styles from "../DeploymentPackageExportView.module.css";

type AuditFilter = "all" | "blocked" | "failed" | "package" | "download" | "cleanup";

export function AuditPanel({ events, loading, onRefresh, onResolveBlocked }: { events: AuditEvent[]; loading: boolean; onRefresh: () => void; onResolveBlocked: (serviceKeys: string[]) => void }) {
  const [filter, setFilter] = useState<AuditFilter>("all");
  const filtered = useMemo(() => events.filter((event) => auditFilterMatches(event, filter)), [events, filter]);
  return (
    <div className={styles.resultPanel}>
      <div className={styles.panelTitleRow}><h3 className={styles.sectionTitle}>最近审计</h3><Button size="small" icon={<i className="ri-shield-check-line" />} loading={loading} onClick={onRefresh}>刷新</Button></div>
      <Segmented size="small" value={filter} options={[{ label: "全部", value: "all" }, { label: "阻断", value: "blocked" }, { label: "失败", value: "failed" }, { label: "导包", value: "package" }, { label: "下载", value: "download" }, { label: "清理", value: "cleanup" }]} onChange={(value) => setFilter(value as AuditFilter)} />
      {filtered.length ? <div className={styles.taskList}>{filtered.map((event) => <AuditItem event={event} key={event.eventId} onResolveBlocked={onResolveBlocked} />)}</div> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无匹配审计日志" />}
    </div>
  );
}

function AuditItem({ event, onResolveBlocked }: { event: AuditEvent; onResolveBlocked: (serviceKeys: string[]) => void }) {
  const services = auditBlockedServices(event);
  return <div className={styles.taskItem}><span className={styles.taskItemMain}><span className={styles.mono}>{auditActionLabel(event.action)}</span><span className={styles.muted}>{event.message || event.targetId || event.createdAt}</span><AuditBlockedServices services={services} /></span><Space size={4} wrap>{event.operator ? <Tag>{event.operator}</Tag> : null}<Tag>{event.createdAt}</Tag><Tag color={auditStatusColor(event.status)}>{event.status}</Tag>{services.length ? <Button size="small" onClick={() => onResolveBlocked(services.map((item) => item.serviceKey))}>处理</Button> : null}</Space></div>;
}

function AuditBlockedServices({ services }: { services: AuditBlockedService[] }) {
  if (!services.length) return null;
  return <div className={styles.auditServiceList}>{services.map((service) => <span className={styles.auditServiceItem} key={service.serviceKey}><strong>{service.serviceName || service.serviceKey}</strong><Tag color={service.buildStatus === "failed" ? "error" : "warning"}>{service.buildStatus || service.status}</Tag>{service.jenkinsUrl ? <Button size="small" href={service.jenkinsUrl} target="_blank">Jenkins</Button> : null}</span>)}</div>;
}

function auditFilterMatches(event: AuditEvent, filter: AuditFilter) {
  if (filter === "all") return true;
  if (filter === "blocked") return event.status === "blocked" || event.action.endsWith(".blocked");
  if (filter === "failed") return event.status === "failed" || event.status === "error";
  if (filter === "package") return event.action.startsWith("package.create");
  if (filter === "download") return event.action.includes("download");
  if (filter === "cleanup") return event.action.includes("cleanup");
  return true;
}

function auditBlockedServices(event: AuditEvent): AuditBlockedService[] {
  const services = event.metadata.services;
  if (event.action !== "package.create.blocked" || !Array.isArray(services)) return [];
  return services.filter((item): item is AuditBlockedService => Boolean(item && typeof item === "object" && "serviceKey" in item));
}

interface AuditBlockedService {
  serviceKey: string;
  serviceName?: string;
  status?: string;
  buildStatus?: string;
  jenkinsUrl?: string;
}
