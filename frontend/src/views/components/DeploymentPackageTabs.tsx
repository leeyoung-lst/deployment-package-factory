import React from "react";
import { Tabs } from "antd";
import type { DeploymentPackageOptions, DeploymentServiceOption, PackagePreview, PackageTask, ProjectProfile, SourceEnv } from "../../api/deploymentPackages";
import { DeploymentExportWorkspace } from "./DeploymentExportWorkspace";
import { PlatformRegistryPanel } from "./PlatformRegistryPanel";
import type { ExportDrawerKey, TargetDraft } from "./deploymentPackageUtils";
import type { useDeploymentPackageActions } from "../hooks/useDeploymentPackageActions";
import type { useDeploymentPackageController } from "../hooks/useDeploymentPackageController";

type Loading = ReturnType<typeof useDeploymentPackageActions>["loading"];

interface Props {
  auditCount: number;
  cleanupFreedBytes?: number;
  controller: ReturnType<typeof useDeploymentPackageController>;
  database: string;
  deployMode: string;
  loading: Loading;
  options: DeploymentPackageOptions | null;
  preview: PackagePreview | null;
  productVersion: string;
  projectKey: string;
  registeredBusinessOptions: DeploymentServiceOption[];
  selectedBusinessOptions: DeploymentServiceOption[];
  selectedDatabaseName?: string;
  selectedPlatformOptions: DeploymentServiceOption[];
  selectedProject: ProjectProfile | null;
  sourceEnv: SourceEnv;
  targetDraft: TargetDraft;
  task: PackageTask | null;
  taskCount: number;
  onCancelTask: () => void;
  onCopyResumeCommand: () => void;
  onDisableBusiness: (item: DeploymentServiceOption) => void;
  onDownloadResumeScript: (shell: "powershell" | "bash") => void;
  onDownloadArtifact: () => void;
  onDownloadChecksum: () => void;
  onOpenDrawer: (drawer: ExportDrawerKey) => void;
  onRefreshPreview: () => void;
  onRetryTask: () => void;
}

export function DeploymentPackageTabs(props: Props) {
  return (
    <div className="panel-body">
      <Tabs items={[platformTab(props), exportTab(props)]} />
    </div>
  );
}

function platformTab(props: Props) {
  return {
    key: "platforms",
    label: "平台注册管理",
    children: <PlatformRegistryPanel options={props.options} loading={props.controller.loadingOptions} registeredBusinessOptions={props.registeredBusinessOptions} onRefresh={() => void props.controller.loadOptions()} onRegister={props.controller.openRegisterModal} onDisable={props.onDisableBusiness} disablingBusinessKey={props.controller.disablingBusinessKey} />,
  };
}

function exportTab(props: Props) {
  return {
    key: "exports",
    label: "项目导出管理",
    children: (
      <DeploymentExportWorkspace
        auditCount={props.auditCount}
        cleanupFreedBytes={props.cleanupFreedBytes}
        database={props.database}
        deployMode={props.deployMode}
        loading={props.loading}
        loadingOptions={props.controller.loadingOptions}
        preview={props.preview}
        productVersion={props.productVersion}
        projectKey={props.projectKey}
        selectedBusinessOptions={props.selectedBusinessOptions}
        selectedDatabaseName={props.selectedDatabaseName}
        selectedPlatformOptions={props.selectedPlatformOptions}
        selectedProject={props.selectedProject}
        sourceEnv={props.sourceEnv}
        targetDraft={props.targetDraft}
        task={props.task}
        taskCount={props.taskCount}
        onCancelTask={props.onCancelTask}
        onCopyResumeCommand={props.onCopyResumeCommand}
        onDownloadResumeScript={props.onDownloadResumeScript}
        onDownloadArtifact={props.onDownloadArtifact}
        onDownloadChecksum={props.onDownloadChecksum}
        onOpenDrawer={props.onOpenDrawer}
        onOpenWizard={props.controller.openExportWizard}
        onRefreshPreview={props.onRefreshPreview}
        onRetryTask={props.onRetryTask}
      />
    ),
  };
}
