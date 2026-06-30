import { useEffect } from "react";
import type { useDeploymentPackageActions } from "./useDeploymentPackageActions";
import type { useDeploymentPackageController } from "./useDeploymentPackageController";
import type { useDeploymentPackageState } from "./useDeploymentPackageState";

type DeploymentState = ReturnType<typeof useDeploymentPackageState>;
type DeploymentActions = ReturnType<typeof useDeploymentPackageActions>;
type DeploymentController = ReturnType<typeof useDeploymentPackageController>;

export function useDeploymentPackageEffects(deploymentState: DeploymentState, actions: DeploymentActions, controller: DeploymentController, notify: NotifyHandlers) {
  const { businessServices, database, deployMode, makePreviewPayload, options, platformServices, productVersion, projectKey, sourceEnv } = deploymentState;
  const { refreshAuditEvents, refreshImageEnvironment, refreshPreview, refreshSelectedTask, refreshTasks, task, tasks } = actions;
  const { loadOptions } = controller;

  useEffect(() => {
    queueMicrotask(() => void loadOptions());
    queueMicrotask(() => void refreshImageEnvironment());
  }, [loadOptions, refreshImageEnvironment]);

  useEffect(() => {
    if (!options) return;
    const payload = options.sourceEnvs.includes(sourceEnv) && database ? makePreviewPayload() : null;
    const timer = window.setTimeout(() => void refreshPreview(payload), 240);
    return () => window.clearTimeout(timer);
  }, [businessServices, database, deployMode, makePreviewPayload, options, platformServices, productVersion, projectKey, refreshPreview, sourceEnv]);

  useEffect(() => {
    if (!actions.preview?.runtimeConfig) return;
    deploymentState.setRuntimeConfig(actions.preview.runtimeConfig);
  }, [actions.preview?.runtimeConfig, deploymentState]);

  useEffect(() => {
    if (!task || task.status === "completed" || task.status === "failed" || task.status === "canceled") return;
    const timer = window.setInterval(() => {
      void refreshSelectedTask(task.taskId).then((payload) => {
        if (!payload) return;
        if (payload.status === "completed") notify.success("部署包生成完成");
        if (payload.status === "failed") notify.error(payload.error || "部署包生成失败");
        if (payload.status === "canceled") notify.info("部署包任务已取消");
      });
    }, 1200);
    return () => window.clearInterval(timer);
  }, [notify, refreshSelectedTask, task]);

  useEffect(() => {
    void refreshTasks();
    void refreshAuditEvents();
  }, [refreshAuditEvents, refreshTasks]);

  useEffect(() => {
    if (!tasks.some((item) => item.status === "pending" || item.status === "running")) return;
    const timer = window.setInterval(() => void refreshTasks(), 3000);
    return () => window.clearInterval(timer);
  }, [refreshTasks, tasks]);
}

interface NotifyHandlers {
  error: (text: string) => void;
  info: (text: string) => void;
  success: (text: string) => void;
}
