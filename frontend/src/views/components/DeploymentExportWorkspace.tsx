import React from "react";
import { Button, Space, Spin } from "antd";
import type { DeploymentServiceOption, PackagePreview, PackageTask, ProjectProfile, SourceEnv } from "../../api/deploymentPackages";
import { DeploymentDraftGrid } from "./DeploymentDraftGrid";
import { DeploymentWorkspaceSide } from "./DeploymentWorkspaceSide";
import { type ExportDrawerKey, type TargetDraft } from "./deploymentPackageUtils";
import styles from "../DeploymentPackageExportView.module.css";

interface Props {
  auditCount: number;
  cleanupFreedBytes?: number;
  database: string;
  deployMode: string;
  loading: WorkspaceLoading;
  loadingOptions: boolean;
  preview: PackagePreview | null;
  productVersion: string;
  projectKey: string;
  selectedBusinessOptions: DeploymentServiceOption[];
  selectedDatabaseName?: string;
  selectedPlatformOptions: DeploymentServiceOption[];
  selectedProject: ProjectProfile | null;
  sourceEnv: SourceEnv;
  targetDraft: TargetDraft;
  task: PackageTask | null;
  taskCount: number;
  onCancelTask: () => void;
  onDownloadArtifact: () => void;
  onDownloadChecksum: () => void;
  onOpenDrawer: (drawer: ExportDrawerKey) => void;
  onOpenWizard: () => void;
  onRefreshPreview: () => void;
  onRetryTask: () => void;
}

export function DeploymentExportWorkspace(props: Props) {
  return (
    <div className={styles.content}>
      <Spin spinning={props.loadingOptions}>
        <div className={styles.exportLaunchPanel}>
          <div className={styles.launchHeader}>
            <span><i className="ri-guide-line" /></span>
            <div><h3>向导式导包</h3><p>按产品范围、平台能力、中间件、目标环境逐步确认，最后创建导包任务。</p></div>
          </div>
          <DeploymentDraftGrid
            database={props.database}
            deployMode={props.deployMode}
            productVersion={props.productVersion}
            projectKey={props.projectKey}
            selectedBusinessOptions={props.selectedBusinessOptions}
            selectedDatabaseName={props.selectedDatabaseName}
            selectedPlatformOptions={props.selectedPlatformOptions}
            selectedProject={props.selectedProject}
            sourceEnv={props.sourceEnv}
            targetDraft={props.targetDraft}
          />
          <Space wrap>
            <Button type="primary" icon={<i className="ri-compass-3-line" />} onClick={props.onOpenWizard}>打开导包向导</Button>
            <Button icon={<i className="ri-eye-line" />} loading={props.loading.preview} onClick={props.onRefreshPreview}>刷新预览</Button>
            <Button icon={<i className="ri-node-tree" />} disabled={!props.preview} onClick={() => props.onOpenDrawer("preview")}>查看依赖图</Button>
          </Space>
        </div>
      </Spin>
      <DeploymentWorkspaceSide
        auditCount={props.auditCount}
        cleanupFreedBytes={props.cleanupFreedBytes}
        loading={props.loading}
        preview={props.preview}
        task={props.task}
        taskCount={props.taskCount}
        onCancelTask={props.onCancelTask}
        onDownloadArtifact={props.onDownloadArtifact}
        onDownloadChecksum={props.onDownloadChecksum}
        onOpenDrawer={props.onOpenDrawer}
        onRefreshPreview={props.onRefreshPreview}
        onRetryTask={props.onRetryTask}
      />
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
