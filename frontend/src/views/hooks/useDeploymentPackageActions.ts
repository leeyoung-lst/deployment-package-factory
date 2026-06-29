import { useCallback, useEffect, useRef, useState } from "react";
import {
  cancelDeploymentPackageTask,
  cleanupDeploymentPackages,
  downloadDeploymentPackage,
  downloadDeploymentPackageChecksum,
  getDeploymentPackageTask,
  getImageExportEnvironment,
  listDeploymentPackageAuditEvents,
  listDeploymentPackageTasks,
  previewDeploymentPackage,
  retryDeploymentPackageTask,
  type AuditEvent,
  type CleanupResult,
  type ImageExportEnvironmentCheck,
  type PackagePreview,
  type PackagePreviewRequest,
  type PackageTask,
} from "../../api/deploymentPackages";
import { mergeTaskIntoList, triggerBrowserDownload } from "../components/deploymentPackageUtils";

export function useDeploymentPackageActions(notify: NotifyHandlers) {
  const [preview, setPreview] = useState<PackagePreview | null>(null);
  const [task, setTask] = useState<PackageTask | null>(null);
  const [tasks, setTasks] = useState<PackageTask[]>([]);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [cleanupResult, setCleanupResult] = useState<CleanupResult | null>(null);
  const [imageEnvironment, setImageEnvironment] = useState<ImageExportEnvironmentCheck | null>(null);
  const [loading, setLoading] = useState({ preview: false, tasks: false, audit: false, cleanup: false, imageEnvironment: false, download: false, checksum: false, taskAction: false });
  const taskRef = useRef<PackageTask | null>(null);
  useEffect(() => { taskRef.current = task; }, [task]);

  const patchLoading = (key: keyof typeof loading, value: boolean) => setLoading((current) => ({ ...current, [key]: value }));
  const refreshImageEnvironment = useCallback(async () => {
    patchLoading("imageEnvironment", true);
    try { setImageEnvironment(await getImageExportEnvironment()); }
    catch (error) { setImageEnvironment({ available: false, exportTool: "", toolVersion: "", dockerVersion: "", message: error instanceof Error ? error.message : "镜像导出环境检查失败" }); }
    finally { patchLoading("imageEnvironment", false); }
  }, []);

  const refreshPreview = useCallback(async (payload: PackagePreviewRequest | null) => {
    if (!payload) { setPreview(null); return; }
    patchLoading("preview", true);
    try { setPreview(await previewDeploymentPackage(payload)); }
    catch (error) { notify.error(error instanceof Error ? error.message : "部署包预览失败"); }
    finally { patchLoading("preview", false); }
  }, [notify]);

  const refreshTasks = useCallback(async () => {
    patchLoading("tasks", true);
    try { setTasks(await listDeploymentPackageTasks(20)); }
    catch (error) { notify.error(error instanceof Error ? error.message : "任务列表刷新失败"); }
    finally { patchLoading("tasks", false); }
  }, [notify]);

  const refreshAuditEvents = useCallback(async () => {
    patchLoading("audit", true);
    try { setAuditEvents(await listDeploymentPackageAuditEvents(20)); }
    catch (error) { notify.error(error instanceof Error ? error.message : "审计日志刷新失败"); }
    finally { patchLoading("audit", false); }
  }, [notify]);

  const refreshSelectedTask = useCallback(async (taskId: string) => {
    try {
      const payload = await getDeploymentPackageTask(taskId);
      setTask(payload);
      setTasks((current) => mergeTaskIntoList(current, payload));
      return payload;
    } catch (error) {
      notify.error(error instanceof Error ? error.message : "任务状态刷新失败");
      return null;
    }
  }, [notify]);

  const cancelTask = useCallback(async () => {
    if (!taskRef.current) return;
    patchLoading("taskAction", true);
    try { const payload = await cancelDeploymentPackageTask(taskRef.current.taskId); setTask(payload); void refreshTasks(); void refreshAuditEvents(); notify.success(payload.status === "canceled" ? "任务已取消" : "已请求取消任务"); }
    catch (error) { notify.error(error instanceof Error ? error.message : "任务取消失败"); }
    finally { patchLoading("taskAction", false); }
  }, [notify, refreshAuditEvents, refreshTasks]);

  const retryTask = useCallback(async () => {
    if (!taskRef.current) return;
    patchLoading("taskAction", true);
    try { const payload = await retryDeploymentPackageTask(taskRef.current.taskId); setTask(payload); void refreshTasks(); void refreshAuditEvents(); notify.success("已创建重试任务"); }
    catch (error) { notify.error(error instanceof Error ? error.message : "任务重试失败"); }
    finally { patchLoading("taskAction", false); }
  }, [notify, refreshAuditEvents, refreshTasks]);

  const runCleanup = useCallback(async (dryRun: boolean) => {
    patchLoading("cleanup", true);
    try { const payload = await cleanupDeploymentPackages(dryRun); setCleanupResult(payload); void refreshTasks(); void refreshAuditEvents(); if (taskRef.current) void refreshSelectedTask(taskRef.current.taskId); notify.success(dryRun ? "清理预演完成" : "清理完成"); }
    catch (error) { notify.error(error instanceof Error ? error.message : "部署包清理失败"); }
    finally { patchLoading("cleanup", false); }
  }, [notify, refreshAuditEvents, refreshSelectedTask, refreshTasks]);

  const downloadTaskArtifact = useCallback(async () => {
    if (!taskRef.current?.result || !taskRef.current.artifactAvailable) return;
    patchLoading("download", true);
    try { triggerBrowserDownload(downloadDeploymentPackage(taskRef.current.result.packageId), `${taskRef.current.result.packageId}.tar.gz`); void refreshAuditEvents(); }
    catch (error) { notify.error(error instanceof Error ? error.message : "部署包下载失败"); }
    finally { patchLoading("download", false); }
  }, [notify, refreshAuditEvents]);

  const downloadTaskChecksum = useCallback(async () => {
    if (!taskRef.current?.result || !taskRef.current.artifactAvailable) return;
    patchLoading("checksum", true);
    try { triggerBrowserDownload(downloadDeploymentPackageChecksum(taskRef.current.result.packageId), `${taskRef.current.result.packageId}.tar.gz.sha256`); void refreshAuditEvents(); }
    catch (error) { notify.error(error instanceof Error ? error.message : "校验文件下载失败"); }
    finally { patchLoading("checksum", false); }
  }, [notify, refreshAuditEvents]);

  return { auditEvents, cancelTask, cleanupResult, downloadTaskArtifact, downloadTaskChecksum, imageEnvironment, loading, preview, refreshAuditEvents, refreshImageEnvironment, refreshPreview, refreshSelectedTask, refreshTasks, retryTask, runCleanup, setTask, task, tasks };
}

interface NotifyHandlers {
  error: (text: string) => void;
  success: (text: string) => void;
}
