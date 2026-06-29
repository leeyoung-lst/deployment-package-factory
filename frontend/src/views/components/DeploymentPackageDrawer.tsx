import React from "react";
import { Drawer } from "antd";
import type { AuditEvent, CleanupResult, PackagePreview, PackageTask, ProjectProfile } from "../../api/deploymentPackages";
import { AuditPanel, CleanupPanel, TaskDetailPanel, TaskListPanel } from "./DeploymentTaskPanels";
import { PreviewSummary } from "./DeploymentPreviewSummary";
import { exportDrawerTitle, type ExportDrawerKey, type TargetDraft } from "./deploymentPackageUtils";

interface Props {
  auditEvents: AuditEvent[];
  cleanupResult: CleanupResult | null;
  drawer: ExportDrawerKey | null;
  loading: DrawerLoading;
  preview: PackagePreview | null;
  project: ProjectProfile | null;
  targetDraft: TargetDraft;
  task: PackageTask | null;
  tasks: PackageTask[];
  onCancelTask: () => void;
  onCleanup: () => void;
  onClose: () => void;
  onDownloadArtifact: () => void;
  onDownloadChecksum: () => void;
  onDryRunCleanup: () => void;
  onRefreshAudit: () => void;
  onRefreshTasks: () => void;
  onRetryTask: () => void;
  onSelectTask: (task: PackageTask) => void;
}

export function DeploymentPackageDrawer(props: Props) {
  return (
    <Drawer title={exportDrawerTitle(props.drawer)} open={Boolean(props.drawer)} onClose={props.onClose} width="min(1080px, 92vw)" destroyOnClose>
      {props.drawer === "preview" && props.preview ? <PreviewSummary preview={props.preview} project={props.project} targetProfile={props.targetDraft} /> : null}
      {props.drawer === "task" ? <TaskDetailPanel task={props.task} taskActionLoading={props.loading.taskAction} downloadLoading={props.loading.download} checksumDownloadLoading={props.loading.checksum} onCancel={props.onCancelTask} onRetry={props.onRetryTask} onDownloadChecksum={props.onDownloadChecksum} onDownloadArtifact={props.onDownloadArtifact} /> : null}
      {props.drawer === "tasks" ? <TaskListPanel tasks={props.tasks} loading={props.loading.tasks} selectedTaskId={props.task?.taskId} onSelect={props.onSelectTask} onRefresh={props.onRefreshTasks} /> : null}
      {props.drawer === "cleanup" ? <CleanupPanel result={props.cleanupResult} loading={props.loading.cleanup} onDryRun={props.onDryRunCleanup} onCleanup={props.onCleanup} /> : null}
      {props.drawer === "audit" ? <AuditPanel events={props.auditEvents} loading={props.loading.audit} onRefresh={props.onRefreshAudit} /> : null}
    </Drawer>
  );
}

interface DrawerLoading {
  audit: boolean;
  checksum: boolean;
  cleanup: boolean;
  download: boolean;
  taskAction: boolean;
  tasks: boolean;
}
