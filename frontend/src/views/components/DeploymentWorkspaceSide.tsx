import React from "react";
import { Button, Empty, Space } from "antd";
import type { PackagePreview, PackageTask } from "../../api/deploymentPackages";
import { ActionTile, PreviewSnapshot, TaskStatusPanel } from "./DeploymentTaskPanels";
import { formatBytes, type ExportDrawerKey } from "./deploymentPackageUtils";
import styles from "../DeploymentPackageExportView.module.css";

interface Props {
  auditCount: number;
  cleanupFreedBytes?: number;
  loading: WorkspaceLoading;
  preview: PackagePreview | null;
  task: PackageTask | null;
  taskCount: number;
  onCancelTask: () => void;
  onCopyResumeCommand: () => void;
  onDownloadArtifact: () => void;
  onDownloadChecksum: () => void;
  onOpenDrawer: (drawer: ExportDrawerKey) => void;
  onRefreshPreview: () => void;
  onRetryTask: () => void;
}

export function DeploymentWorkspaceSide(props: Props) {
  return (
    <div className={styles.workspace}>
      <div className={styles.previewPanel}>
        <div className={styles.panelTitleRow}>
          <h3 className={styles.sectionTitle}>依赖预览</h3>
          <Space>
            <Button size="small" icon={<i className="ri-eye-line" />} loading={props.loading.preview} onClick={props.onRefreshPreview}>预览</Button>
            <Button size="small" icon={<i className="ri-node-tree" />} disabled={!props.preview} onClick={() => props.onOpenDrawer("preview")}>详情</Button>
          </Space>
        </div>
        {props.preview ? <PreviewSnapshot preview={props.preview} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无预览" />}
      </div>
      <TaskStatusPanel task={props.task} taskActionLoading={props.loading.taskAction} downloadLoading={props.loading.download} checksumDownloadLoading={props.loading.checksum} onOpenDetail={() => props.onOpenDrawer("task")} onCancel={props.onCancelTask} onRetry={props.onRetryTask} onCopyResumeCommand={props.onCopyResumeCommand} onDownloadChecksum={props.onDownloadChecksum} onDownloadArtifact={props.onDownloadArtifact} />
      <div className={styles.toolGrid}>
        <ActionTile icon="ri-list-check-3" title="最近任务" value={`${props.taskCount} 条`} actionLabel="打开" loading={props.loading.tasks} onAction={() => props.onOpenDrawer("tasks")} />
        <ActionTile icon="ri-delete-bin-6-line" title="产物清理" value={props.cleanupFreedBytes !== undefined ? `释放 ${formatBytes(props.cleanupFreedBytes)}` : "待预演"} actionLabel="打开" loading={props.loading.cleanup} onAction={() => props.onOpenDrawer("cleanup")} />
        <ActionTile icon="ri-shield-check-line" title="最近审计" value={`${props.auditCount} 条`} actionLabel="打开" loading={props.loading.audit} onAction={() => props.onOpenDrawer("audit")} />
      </div>
    </div>
  );
}

interface WorkspaceLoading {
  audit: boolean;
  checksum: boolean;
  cleanup: boolean;
  download: boolean;
  preview: boolean;
  taskAction: boolean;
  tasks: boolean;
}
