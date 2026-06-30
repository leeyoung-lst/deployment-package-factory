import React from "react";
import { Drawer } from "antd";
import type { AuditEvent, AuditEventQuery, CleanupResult, PackagePreview, PackageTask, ProjectProfile } from "../../api/deploymentPackages";
import { CleanupPanel, TaskDetailPanel, TaskListPanel } from "./DeploymentTaskPanels";
import { AuditPanel } from "./AuditPanel";
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
  onAuditFilterChange: (query: AuditEventQuery) => void;
  onCancelTask: () => void;
  onCleanup: () => void;
  onClose: () => void;
  onCopyResumeCommand: () => void;
  onDownloadArtifact: () => void;
  onDownloadChecksum: () => void;
  onDryRunCleanup: () => void;
  onRefreshAudit: () => void;
  onRefreshTasks: () => void;
  onResolveBlockedAudit: (serviceKeys: string[]) => void;
  onRetryTask: () => void;
  onSelectTask: (task: PackageTask) => void;
}

export function DeploymentPackageDrawer(props: Props) {
  return (
    <Drawer title={exportDrawerTitle(props.drawer)} open={Boolean(props.drawer)} onClose={props.onClose} width="min(1080px, 92vw)" destroyOnClose>
      {props.drawer === "preview" && props.preview ? <PreviewSummary preview={props.preview} project={props.project} targetProfile={props.targetDraft} /> : null}
      {props.drawer === "task" ? <TaskDetailPanel task={props.task} taskActionLoading={props.loading.taskAction} downloadLoading={props.loading.download} checksumDownloadLoading={props.loading.checksum} onCancel={props.onCancelTask} onRetry={props.onRetryTask} onCopyResumeCommand={props.onCopyResumeCommand} onDownloadChecksum={props.onDownloadChecksum} onDownloadArtifact={props.onDownloadArtifact} /> : null}
      {props.drawer === "tasks" ? <TaskListPanel tasks={props.tasks} loading={props.loading.tasks} selectedTaskId={props.task?.taskId} onSelect={props.onSelectTask} onRefresh={props.onRefreshTasks} /> : null}
      {props.drawer === "cleanup" ? <CleanupPanel result={props.cleanupResult} loading={props.loading.cleanup} onDryRun={props.onDryRunCleanup} onCleanup={props.onCleanup} /> : null}
      {props.drawer === "audit" ? <AuditPanel events={props.auditEvents} loading={props.loading.audit} onFilterChange={props.onAuditFilterChange} onRefresh={props.onRefreshAudit} onResolveBlocked={props.onResolveBlockedAudit} /> : null}
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
