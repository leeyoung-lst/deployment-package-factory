import React from "react";
import { Button, Empty, Popconfirm, Progress, Space, Tag } from "antd";
import type { CleanupResult, PackageTask } from "../../api/deploymentPackages";
import { formatBytes, taskStatusColor } from "./deploymentPackageUtils";
import styles from "../DeploymentPackageExportView.module.css";

export function ValidationSummary({ result }: { result: NonNullable<PackageTask["result"]> }) {
  const summary = result.validationSummary || {};
  const artifactSize = summary.artifactSize || result.artifactSize || 0;
  return (
    <div className={styles.validationSummary}>
      <Metric label="包大小" value={formatBytes(artifactSize)} />
      <Metric label="索引文件" value={summary.packageIndexFileCount ?? 0} />
      <Metric label="镜像条目" value={summary.imageEntryCount ?? 0} />
      <Metric label="镜像归档" value={summary.imageArchiveCount ?? 0} />
      <Metric label="缺失归档" value={summary.missingImageArchiveCount ?? 0} />
    </div>
  );
}

export function PreviewSnapshot({ preview }: { preview: { platformServices: unknown[]; businessServices: unknown[]; middleware: unknown[]; imageEntries: Array<{ sourceMissing?: boolean }>; database: { name: string; domestic: boolean } } }) {
  const missingImages = preview.imageEntries.filter((item) => item.sourceMissing).length;
  return <div className={styles.snapshotGrid}><Metric label="基础平台" value={preview.platformServices.length} /><Metric label="业务平台" value={preview.businessServices.length} /><Metric label="中间件" value={preview.middleware.length} /><Metric label="镜像条目" value={preview.imageEntries.length} /><div className={styles.summaryRow}><span className={styles.muted}>数据库</span><Space size={6} wrap><Tag color={preview.database.domestic ? "red" : "blue"}>{preview.database.name}</Tag>{missingImages ? <Tag color="red">{missingImages} 个镜像未匹配</Tag> : <Tag color="green">镜像已匹配</Tag>}</Space></div></div>;
}

export function TaskStatusPanel(props: TaskPanelProps & { onOpenDetail: () => void }) {
  return <div className={styles.resultPanel}><div className={styles.panelTitleRow}><h3 className={styles.sectionTitle}>当前任务</h3><Button size="small" icon={<i className="ri-file-list-3-line" />} disabled={!props.task} onClick={props.onOpenDetail}>详情</Button></div>{props.task ? <TaskBody {...props} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无任务" />}</div>;
}

export function TaskDetailPanel(props: TaskPanelProps) {
  if (!props.task) return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="请选择任务" />;
  return <div className={styles.resultPanel}><TaskBody {...props} detail /></div>;
}

function TaskBody(props: TaskPanelProps & { detail?: boolean }) {
  const task = props.task!;
  return (
    <>
      <ResultRow label="任务 ID"><span className={styles.mono}>{task.taskId}</span></ResultRow>
      <ResultRow label="状态"><Space size={6} wrap><Tag color={taskStatusColor(task.status)}>{task.status}</Tag><span>{task.message}</span></Space></ResultRow>
      <ResultRow label="镜像模式"><Tag color={taskImageMode(task) === "image-archive" ? "green" : "blue"}>{taskImageMode(task) === "image-archive" ? "镜像归档" : "镜像清单"}</Tag></ResultRow>
      <Progress percent={task.progress} status={task.status === "failed" ? "exception" : task.status === "completed" ? "success" : "active"} />
      {task.result ? <ValidationSummary result={task.result} /> : null}
      {props.detail && task.result ? <TaskResultDetails task={task} /> : null}
      {props.detail && task.error ? <ResultRow label="错误"><span className={styles.mono}>{task.error}</span></ResultRow> : null}
      {props.detail ? <ResultRow label="日志"><div className={styles.logBox}>{task.logs.map((item, index) => <div key={`${index}-${item}`} className={styles.mono}>{item}</div>)}</div></ResultRow> : null}
      <TaskActions {...props} task={task} />
    </>
  );
}

function TaskResultDetails({ task }: { task: PackageTask }) {
  if (!task.result) return null;
  return <><ResultRow label="包 ID"><span className={styles.mono}>{task.result.packageId}</span></ResultRow><ResultRow label="SHA256"><span className={styles.mono}>{task.result.sha256}</span></ResultRow><ResultRow label="产物路径"><Space direction="vertical" size={4}><span className={styles.mono}>{task.result.artifactPath}</span>{task.result.checksumPath ? <span className={styles.mono}>{task.result.checksumPath}</span> : null}<Tag color={task.artifactAvailable ? "green" : "default"}>{task.artifactAvailable ? "可下载" : "产物已清理"}</Tag></Space></ResultRow></>;
}

function taskImageMode(task: PackageTask) {
  return String(task.result?.manifest?.imageMode || task.request.imageMode || "image-archive");
}

interface TaskPanelProps {
  task: PackageTask | null;
  taskActionLoading: boolean;
  downloadLoading: boolean;
  checksumDownloadLoading: boolean;
  onCancel: () => void;
  onRetry: () => void;
  onCopyResumeCommand: () => void;
  onDownloadChecksum: () => void;
  onDownloadArtifact: () => void;
}

function TaskActions(props: TaskPanelProps & { task: PackageTask }) {
  const task = props.task;
  return <div className={styles.actions}><Button icon={<i className="ri-close-circle-line" />} loading={props.taskActionLoading} disabled={task.status !== "pending" && task.status !== "running"} onClick={props.onCancel}>取消任务</Button><Button icon={<i className="ri-restart-line" />} loading={props.taskActionLoading} disabled={task.status !== "failed" && task.status !== "canceled"} onClick={props.onRetry}>重试任务</Button><Button icon={<i className="ri-file-copy-line" />} onClick={props.onCopyResumeCommand} disabled={!task.result || !task.artifactAvailable}>复制续传命令</Button><Button icon={<i className="ri-file-shield-2-line" />} loading={props.checksumDownloadLoading} onClick={props.onDownloadChecksum} disabled={!task.result || !task.artifactAvailable}>下载校验文件</Button><Button type="primary" icon={<i className="ri-download-line" />} loading={props.downloadLoading} onClick={props.onDownloadArtifact} disabled={!task.result || !task.artifactAvailable}>{task.result && !task.artifactAvailable ? "产物已清理" : "下载部署包"}</Button></div>;
}

export function ActionTile({ icon, title, value, actionLabel, loading, onAction }: { icon: string; title: string; value: string; actionLabel: string; loading: boolean; onAction: () => void }) {
  return <div className={styles.actionTile}><i className={icon} /><span><strong>{title}</strong><span className={styles.muted}>{value}</span></span><Button size="small" loading={loading} onClick={onAction}>{actionLabel}</Button></div>;
}

export function TaskListPanel({ tasks, loading, selectedTaskId, onSelect, onRefresh }: { tasks: PackageTask[]; loading: boolean; selectedTaskId?: string; onSelect: (task: PackageTask) => void; onRefresh: () => void }) {
  return <div className={styles.resultPanel}><div className={styles.panelTitleRow}><h3 className={styles.sectionTitle}>最近任务</h3><Button size="small" icon={<i className="ri-refresh-line" />} loading={loading} onClick={onRefresh}>刷新</Button></div>{tasks.length ? <div className={styles.taskList}>{tasks.map((item) => <button key={item.taskId} type="button" className={`${styles.taskItem} ${item.taskId === selectedTaskId ? styles.taskItemActive : ""}`} onClick={() => onSelect(item)}><span className={styles.taskItemMain}><span className={styles.mono}>{item.result?.packageId || item.taskId}</span><span className={styles.muted}>{item.message || item.updatedAt}</span></span><Space size={4}>{item.result && !item.artifactAvailable ? <Tag>已清理</Tag> : null}<Tag color={taskStatusColor(item.status)}>{item.status}</Tag></Space></button>)}</div> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无任务" />}</div>;
}

export function CleanupPanel({ result, loading, onDryRun, onCleanup }: { result: CleanupResult | null; loading: boolean; onDryRun: () => void; onCleanup: () => void }) {
  return <div className={styles.resultPanel}><div className={styles.panelTitleRow}><h3 className={styles.sectionTitle}>产物清理</h3><Space><Button size="small" icon={<i className="ri-search-eye-line" />} loading={loading} onClick={onDryRun}>预演</Button><Popconfirm title="确认清理部署包产物？" description="任务记录会保留，已清理的包不能继续下载。" onConfirm={onCleanup}><Button size="small" danger icon={<i className="ri-delete-bin-line" />} loading={loading}>清理</Button></Popconfirm></Space></div>{result ? <CleanupSummary result={result} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="先执行清理预演" />}</div>;
}

function CleanupSummary({ result }: { result: CleanupResult }) {
  return <div className={styles.cleanupSummary}><Metric label="扫描任务" value={result.scannedTasks} /><Metric label="产物" value={result.deletedArtifacts} /><Metric label="临时目录" value={result.deletedWorkDirs} /><Metric label="释放" value={formatBytes(result.freedBytes)} /><ResultRow label="模式"><Tag color={result.dryRun ? "blue" : "green"}>{result.dryRun ? "dry-run" : "executed"}</Tag></ResultRow><ResultRow label="路径"><div className={styles.logBox}>{result.deletedPaths.length ? result.deletedPaths.slice(0, 20).map((item) => <div key={item} className={styles.mono}>{item}</div>) : <span className={styles.muted}>没有需要清理的产物</span>}</div></ResultRow></div>;
}

function Metric({ label, value }: { label: string; value: React.ReactNode }) {
  return <div className={styles.metricItem}><span className={styles.muted}>{label}</span><strong>{value}</strong></div>;
}

function ResultRow({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className={styles.resultRow}><span className={styles.muted}>{label}</span><span>{children}</span></div>;
}
