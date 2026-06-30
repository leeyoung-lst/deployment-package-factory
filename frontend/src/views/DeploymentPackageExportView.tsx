import React, { useMemo, useState } from "react";
import { App, Form } from "antd";
import { DeploymentPackageDrawer } from "./components/DeploymentPackageDrawer";
import { DeploymentPackageHeader } from "./components/DeploymentPackageHeader";
import { DeploymentPackageModals } from "./components/DeploymentPackageModals";
import { DeploymentPackageTabs } from "./components/DeploymentPackageTabs";
import { type ExportDrawerKey } from "./components/deploymentPackageUtils";
import { useDeploymentPackageActions } from "./hooks/useDeploymentPackageActions";
import { useDeploymentPackageController } from "./hooks/useDeploymentPackageController";
import { useDeploymentPackageEffects } from "./hooks/useDeploymentPackageEffects";
import { useDeploymentPackageState } from "./hooks/useDeploymentPackageState";
import styles from "./DeploymentPackageExportView.module.css";


export const DeploymentPackageExportView: React.FC = () => {
  const { message } = App.useApp();
  const [form] = Form.useForm();
  const [registerForm] = Form.useForm();
  const [exportDrawer, setExportDrawer] = useState<ExportDrawerKey | null>(null);
  const notify = useMemo(() => ({ error: message.error, info: message.info, success: message.success, warning: message.warning }), [message]);
  const actions = useDeploymentPackageActions(notify);
  const { auditEvents, cancelTask, cleanupResult, downloadTaskArtifact, downloadTaskChecksum, imageEnvironment, loading, preview, refreshAuditEvents, refreshImageEnvironment, refreshPreview, refreshTasks, retryTask, runCleanup, setTask, task, tasks } = actions;
  const deploymentState = useDeploymentPackageState(form);
  const {
    database,
    deployMode,
    makePreviewPayload,
    options,
    productVersion,
    projectKey,
    registeredBusinessOptions,
    selectedBusinessOptions,
    selectedDatabaseOption,
    selectedPlatformOptions,
    selectedProject,
    sourceEnv,
    targetDraft,
  } = deploymentState;

  const controller = useDeploymentPackageController(form, registerForm, deploymentState, actions, notify);
  useDeploymentPackageEffects(deploymentState, actions, controller, notify);

  return (
    <section className={`panel ${styles.page}`}>
      <DeploymentPackageHeader
        building={controller.building}
        imageEnvironmentLoading={loading.imageEnvironment}
        loadingOptions={controller.loadingOptions}
        tasksLoading={loading.tasks}
        onBuild={controller.openExportWizard}
        onRefreshImageEnvironment={() => void refreshImageEnvironment()}
        onRefreshOptions={() => void controller.loadOptions()}
        onRefreshTasks={() => void refreshTasks()}
        onRegisterBusiness={controller.openRegisterModal}
      />

      <DeploymentPackageTabs
        auditCount={auditEvents.length}
        cleanupFreedBytes={cleanupResult?.freedBytes}
        controller={controller}
        database={database}
        deployMode={deployMode}
        loading={loading}
        options={options}
        preview={preview}
        productVersion={productVersion}
        projectKey={projectKey}
        registeredBusinessOptions={registeredBusinessOptions}
        selectedBusinessOptions={selectedBusinessOptions}
        selectedDatabaseName={selectedDatabaseOption?.name}
        selectedPlatformOptions={selectedPlatformOptions}
        selectedProject={selectedProject}
        sourceEnv={sourceEnv}
        targetDraft={targetDraft}
        task={task}
        taskCount={tasks.length}
        onCancelTask={() => void cancelTask()}
        onDisableBusiness={(item) => void controller.disableBusiness(item)}
        onDownloadArtifact={() => void downloadTaskArtifact()}
        onDownloadChecksum={() => void downloadTaskChecksum()}
        onOpenDrawer={setExportDrawer}
        onRefreshPreview={() => void refreshPreview(makePreviewPayload())}
        onRetryTask={() => void retryTask()}
      />

      <DeploymentPackageDrawer
        auditEvents={auditEvents}
        cleanupResult={cleanupResult}
        drawer={exportDrawer}
        loading={loading}
        preview={preview}
        project={selectedProject}
        targetDraft={targetDraft}
        task={task}
        tasks={tasks}
        onAuditFilterChange={(query) => void refreshAuditEvents(query)}
        onCancelTask={() => void cancelTask()}
        onCleanup={() => void runCleanup(false)}
        onClose={() => setExportDrawer(null)}
        onDownloadArtifact={() => void downloadTaskArtifact()}
        onDownloadChecksum={() => void downloadTaskChecksum()}
        onDryRunCleanup={() => void runCleanup(true)}
        onRefreshAudit={() => void refreshAuditEvents()}
        onRefreshTasks={() => void refreshTasks()}
        onResolveBlockedAudit={(serviceKeys) => {
          controller.openBlockedMicroservices(serviceKeys);
          setExportDrawer(null);
        }}
        onRetryTask={() => void retryTask()}
        onSelectTask={(item) => {
          setTask(item);
          setExportDrawer("task");
        }}
      />

      <DeploymentPackageModals
        controller={controller}
        deploymentState={deploymentState}
        form={form}
        imageEnvironment={imageEnvironment}
        imageEnvironmentLoading={loading.imageEnvironment}
        options={options}
        preview={preview}
        previewing={loading.preview}
        registerForm={registerForm}
        onRefreshPreview={() => void refreshPreview(makePreviewPayload())}
      />
    </section>
  );
};
