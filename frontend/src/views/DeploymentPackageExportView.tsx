import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { App, Button, Checkbox, Drawer, Empty, Form, Popconfirm, Space, Spin, Tabs, Tag } from "antd";
import type { CheckboxChangeEvent } from "antd/es/checkbox";
import {
  cancelDeploymentPackageTask,
  cleanupDeploymentPackages,
  createDeploymentPackage,
  downloadDeploymentPackage,
  downloadDeploymentPackageChecksum,
  getImageExportEnvironment,
  getDeploymentPackageOptions,
  getDeploymentPackageTask,
  listDeploymentPackageAuditEvents,
  listDeploymentPackageTasks,
  previewDeploymentPackage,
  registerBusinessPlatform,
  retryDeploymentPackageTask,
  disableBusinessPlatform,
  type AuditEvent,
  type BusinessSelection,
  type CleanupResult,
  type DeployMode,
  type DeploymentPackageOptions,
  type DeploymentServiceOption,
  type ImageExportEnvironmentCheck,
  type PackagePreview,
  type PackagePreviewRequest,
  type PackageTask,
  type ProjectProfile,
  type SourceEnv,
} from "../api/deploymentPackages";
import { getSystemSettings, type SystemSettings } from "../api/settings";
import { BusinessPlatformRegistrationModal } from "./components/BusinessPlatformRegistrationModal";
import { DependencyGraph } from "./components/DeploymentDependencyGraph";
import { DeploymentPackageWizardModal } from "./components/DeploymentPackageWizardModal";
import { DraftItem } from "./components/DeploymentPackageWizardSteps";
import {
  ActionTile,
  AuditPanel,
  CleanupPanel,
  PreviewSnapshot,
  TaskDetailPanel,
  TaskListPanel,
  TaskStatusPanel,
} from "./components/DeploymentTaskPanels";
import {
  auditStatusColor,
  businessOptionsForEnv,
  businessOptionValue,
  businessPlatformRowKey,
  exportDrawerTitle,
  DEFAULT_IMAGE_MODE,
  DEFAULT_TARGET,
  EXPORT_WIZARD_STEPS,
  formatBytes,
  mergeTaskIntoList,
  parseBusinessOptionValue,
  serviceOptionsForEnv,
  taskStatusColor,
  triggerBrowserDownload,
  type ExportDrawerKey,
  type TargetDraft,
} from "./components/deploymentPackageUtils";
import styles from "./DeploymentPackageExportView.module.css";


export const DeploymentPackageExportView: React.FC = () => {
  const { message } = App.useApp();
  const [form] = Form.useForm();
  const [registerForm] = Form.useForm();
  const [options, setOptions] = useState<DeploymentPackageOptions | null>(null);
  const [projectKey, setProjectKey] = useState("");
  const [productVersion, setProductVersion] = useState("");
  const [sourceEnv, setSourceEnv] = useState<SourceEnv>("test");
  const [deployMode, setDeployMode] = useState<DeployMode>("k8s");
  const [platformServices, setPlatformServices] = useState<string[]>([]);
  const [businessServices, setBusinessServices] = useState<string[]>([]);
  const [database, setDatabase] = useState("");
  const [preview, setPreview] = useState<PackagePreview | null>(null);
  const [task, setTask] = useState<PackageTask | null>(null);
  const [tasks, setTasks] = useState<PackageTask[]>([]);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [cleanupResult, setCleanupResult] = useState<CleanupResult | null>(null);
  const [imageEnvironment, setImageEnvironment] = useState<ImageExportEnvironmentCheck | null>(null);
  const [loadingOptions, setLoadingOptions] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [building, setBuilding] = useState(false);
  const [taskActionLoading, setTaskActionLoading] = useState(false);
  const [tasksLoading, setTasksLoading] = useState(false);
  const [auditLoading, setAuditLoading] = useState(false);
  const [cleanupLoading, setCleanupLoading] = useState(false);
  const [imageEnvironmentLoading, setImageEnvironmentLoading] = useState(false);
  const [downloadLoading, setDownloadLoading] = useState(false);
  const [checksumDownloadLoading, setChecksumDownloadLoading] = useState(false);
  const [registeringBusiness, setRegisteringBusiness] = useState(false);
  const [registerModalOpen, setRegisterModalOpen] = useState(false);
  const [exportWizardOpen, setExportWizardOpen] = useState(false);
  const [exportStep, setExportStep] = useState(0);
  const [exportDrawer, setExportDrawer] = useState<ExportDrawerKey | null>(null);
  const [disablingBusinessKey, setDisablingBusinessKey] = useState("");
  const [targetDraft, setTargetDraft] = useState<TargetDraft>({ ...DEFAULT_TARGET, imageMode: DEFAULT_IMAGE_MODE });
  const [systemSettings, setSystemSettings] = useState<SystemSettings | null>(null);

  const requiredPlatformKeys = useMemo(
    () => options?.platformServices.filter((item) => item.required).map((item) => item.key) ?? [],
    [options],
  );
  const selectedProject = useMemo(
    () => options?.projects.find((item) => item.key === projectKey) ?? null,
    [options?.projects, projectKey],
  );
  const businessOptionsForSourceEnv = useMemo(
    () => businessOptionsForEnv(options?.businessServices ?? [], sourceEnv),
    [options?.businessServices, sourceEnv],
  );
  const platformOptionsForSourceEnv = useMemo(
    () => serviceOptionsForEnv(options?.platformServices ?? [], sourceEnv),
    [options?.platformServices, sourceEnv],
  );
  const databaseOptionsForSourceEnv = useMemo(
    () => serviceOptionsForEnv(options?.databaseOptions ?? [], sourceEnv),
    [options?.databaseOptions, sourceEnv],
  );
  const registeredBusinessOptions = useMemo(
    () => (options?.businessServices ?? []).filter((item) => item.registered && item.status !== "disabled"),
    [options?.businessServices],
  );
  const selectedPlatformOptions = useMemo(
    () => platformOptionsForSourceEnv.filter((item) => platformServices.includes(item.key)),
    [platformOptionsForSourceEnv, platformServices],
  );
  const selectedBusinessOptions = useMemo(
    () => businessServices
      .map((value) => options?.businessServices.find((item) => businessOptionValue(item) === value))
      .filter((item): item is DeploymentServiceOption => Boolean(item)),
    [businessServices, options?.businessServices],
  );
  const selectedDatabaseOption = useMemo(
    () => databaseOptionsForSourceEnv.find((item) => item.key === database) ?? null,
    [database, databaseOptionsForSourceEnv],
  );
  const defaultTargetRegistry = useCallback(
    (project?: ProjectProfile | null, settingsOverride?: SystemSettings | null) => project?.registry || settingsOverride?.harbor.registry || systemSettings?.harbor.registry || "",
    [systemSettings?.harbor.registry],
  );

  const makePreviewPayload = useCallback((): PackagePreviewRequest => {
    const selectedBusiness: BusinessSelection[] = businessServices.map((value) => {
      const item = options?.businessServices.find((candidate) => businessOptionValue(candidate) === value);
      const fallback = parseBusinessOptionValue(value);
      return { name: item?.key || fallback.key, profile: item?.profile || fallback.profile };
    });
    const { imageMode, ...previewTargetProfile } = targetDraft;
    return {
      projectKey,
      productVersion,
      sourceEnv,
      deployModes: [deployMode],
      platformServices,
      businessServices: selectedBusiness,
      database,
      targetProfile: {
        ...previewTargetProfile,
        exportImages: imageMode === "image-archive",
      },
    };
  }, [businessServices, database, deployMode, options?.businessServices, platformServices, productVersion, projectKey, sourceEnv, targetDraft]);

  const applyProjectDefaults = useCallback((key: string, sourceOptions = options) => {
    const project = sourceOptions?.projects.find((item) => item.key === key);
    setProjectKey(key);
    if (!project) return;
    setProductVersion(project.defaultVersion || project.versions[0] || "");
    setSourceEnv(project.defaultSourceEnv);
    setDeployMode(project.defaultDeployModes[0] || "k8s");
    setPlatformServices(project.defaultPlatformServices.filter((key) => serviceOptionsForEnv(sourceOptions?.platformServices ?? [], project.defaultSourceEnv).some((item) => item.key === key)));
    setBusinessServices(
      project.defaultBusinessServices
        .map((item) => businessOptionValue({ key: item.name, profile: item.profile }))
        .filter((value) => businessOptionsForEnv(sourceOptions?.businessServices ?? [], project.defaultSourceEnv).some((item) => businessOptionValue(item) === value)),
    );
    const projectDatabases = serviceOptionsForEnv(sourceOptions?.databaseOptions ?? [], project.defaultSourceEnv);
    setDatabase(projectDatabases.some((item) => item.key === project.defaultDatabase) ? project.defaultDatabase : (projectDatabases[0]?.key ?? ""));
    form.setFieldsValue({
      domain: project.domain,
      registry: defaultTargetRegistry(project),
      namespacePrefix: project.namespacePrefix,
      storageClass: project.storageClass,
    });
    setTargetDraft((current) => ({
      ...current,
      domain: project.domain,
      registry: defaultTargetRegistry(project),
      namespacePrefix: project.namespacePrefix,
      storageClass: project.storageClass,
    }));
  }, [defaultTargetRegistry, form, options]);

  const applyProjectDefaultsFromOptions = useCallback((key: string, sourceOptions: DeploymentPackageOptions, settingsOverride?: SystemSettings | null) => {
    const project = sourceOptions.projects.find((item) => item.key === key);
    setProjectKey(key);
    if (!project) return;
    setProductVersion(project.defaultVersion || project.versions[0] || "");
    setSourceEnv(project.defaultSourceEnv);
    setDeployMode(project.defaultDeployModes[0] || "k8s");
    setPlatformServices(project.defaultPlatformServices.filter((key) => serviceOptionsForEnv(sourceOptions.platformServices, project.defaultSourceEnv).some((item) => item.key === key)));
    setBusinessServices(
      project.defaultBusinessServices
        .map((item) => businessOptionValue({ key: item.name, profile: item.profile }))
        .filter((value) => businessOptionsForEnv(sourceOptions.businessServices, project.defaultSourceEnv).some((item) => businessOptionValue(item) === value)),
    );
    const projectDatabases = serviceOptionsForEnv(sourceOptions.databaseOptions, project.defaultSourceEnv);
    setDatabase(projectDatabases.some((item) => item.key === project.defaultDatabase) ? project.defaultDatabase : (projectDatabases[0]?.key ?? ""));
    form.setFieldsValue({
      domain: project.domain,
      registry: defaultTargetRegistry(project, settingsOverride),
      namespacePrefix: project.namespacePrefix,
      storageClass: project.storageClass,
    });
    setTargetDraft((current) => ({
      ...current,
      domain: project.domain,
      registry: defaultTargetRegistry(project, settingsOverride),
      namespacePrefix: project.namespacePrefix,
      storageClass: project.storageClass,
    }));
  }, [defaultTargetRegistry, form]);

  const loadOptions = useCallback(async () => {
    setLoadingOptions(true);
    try {
      const [payload, settingsPayload] = await Promise.all([getDeploymentPackageOptions(), getSystemSettings()]);
      setOptions(payload);
      setSystemSettings(settingsPayload);
      const nextSourceEnv = payload.sourceEnvs.includes(sourceEnv) ? sourceEnv : (payload.sourceEnvs[0] ?? "test");
      setSourceEnv(nextSourceEnv);
      const runtimePlatform = serviceOptionsForEnv(payload.platformServices, nextSourceEnv);
      const required = runtimePlatform.filter((item) => item.required).map((item) => item.key);
      setPlatformServices((current) => Array.from(new Set([...required, ...current])));
      const runtimeBusiness = businessOptionsForEnv(payload.businessServices, nextSourceEnv);
      setBusinessServices((current) => current.filter((value) => runtimeBusiness.some((item) => businessOptionValue(item) === value)));
      const runtimeDatabases = serviceOptionsForEnv(payload.databaseOptions, nextSourceEnv);
      if (runtimeDatabases.some((item) => item.key === "postgres")) {
        setDatabase("postgres");
      } else if (runtimeDatabases[0]) {
        setDatabase(runtimeDatabases[0].key);
      } else {
        setDatabase("");
      }
      if (payload.projects[0]) {
        applyProjectDefaultsFromOptions(payload.projects[0].key, payload, settingsPayload);
      } else {
        setProjectKey("");
        setProductVersion("");
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : "部署包选项加载失败");
    } finally {
      setLoadingOptions(false);
    }
  }, [applyProjectDefaultsFromOptions, message, sourceEnv]);

  const refreshImageEnvironment = useCallback(async () => {
    setImageEnvironmentLoading(true);
    try {
      const payload = await getImageExportEnvironment();
      setImageEnvironment(payload);
    } catch (error) {
      setImageEnvironment({
        available: false,
        exportTool: "",
        toolVersion: "",
        dockerVersion: "",
        message: error instanceof Error ? error.message : "镜像导出环境检查失败",
      });
    } finally {
      setImageEnvironmentLoading(false);
    }
  }, []);
  const loadOptionsRef = useRef(loadOptions);
  const refreshImageEnvironmentRef = useRef(refreshImageEnvironment);

  useEffect(() => {
    loadOptionsRef.current = loadOptions;
  }, [loadOptions]);

  useEffect(() => {
    refreshImageEnvironmentRef.current = refreshImageEnvironment;
  }, [refreshImageEnvironment]);

  const refreshPreview = useCallback(async () => {
    if (!options) return;
    if (!options.sourceEnvs.includes(sourceEnv) || !database) {
      setPreview(null);
      return;
    }
    setPreviewing(true);
    try {
      const payload = await previewDeploymentPackage(makePreviewPayload());
      setPreview(payload);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "部署包预览失败");
    } finally {
      setPreviewing(false);
    }
  }, [makePreviewPayload, message, options]);

  const refreshTasks = useCallback(async () => {
    setTasksLoading(true);
    try {
      const payload = await listDeploymentPackageTasks(20);
      setTasks(payload);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "任务列表刷新失败");
    } finally {
      setTasksLoading(false);
    }
  }, [message]);

  const refreshAuditEvents = useCallback(async () => {
    setAuditLoading(true);
    try {
      const payload = await listDeploymentPackageAuditEvents(20);
      setAuditEvents(payload);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "审计日志刷新失败");
    } finally {
      setAuditLoading(false);
    }
  }, [message]);

  const refreshSelectedTask = useCallback(async (taskId: string) => {
    try {
      const payload = await getDeploymentPackageTask(taskId);
      setTask(payload);
      setTasks((current) => mergeTaskIntoList(current, payload));
      return payload;
    } catch (error) {
      message.error(error instanceof Error ? error.message : "任务状态刷新失败");
      return null;
    }
  }, [message]);

  useEffect(() => {
    queueMicrotask(() => void loadOptionsRef.current());
    queueMicrotask(() => void refreshImageEnvironmentRef.current());
  }, []);

  useEffect(() => {
    if (!options) return;
    const timer = window.setTimeout(() => void refreshPreview(), 240);
    return () => window.clearTimeout(timer);
  }, [businessServices, database, deployMode, options, platformServices, productVersion, projectKey, refreshPreview, sourceEnv]);

  const onPlatformChange = (checkedValues: Array<string | number | boolean>) => {
    const selected = checkedValues.map(String);
    setPlatformServices(Array.from(new Set([...requiredPlatformKeys, ...selected])));
  };

  const onBusinessChange = (checkedValues: Array<string | number | boolean>) => {
    setBusinessServices(checkedValues.map(String));
  };

  const openExportWizard = () => {
    form.setFieldsValue({ ...DEFAULT_TARGET, ...targetDraft, imageMode: targetDraft.imageMode ?? DEFAULT_IMAGE_MODE });
    setExportStep(0);
    setExportWizardOpen(true);
  };

  const validateExportStep = async (step = exportStep) => {
    if (step === 0) {
      if (options?.projects.length && !projectKey) {
        message.warning("请选择项目");
        return false;
      }
      if ((selectedProject?.versions.length ?? 0) > 0 && !productVersion) {
        message.warning("请选择产品版本");
        return false;
      }
      if (!sourceEnv) {
        message.warning("请选择来源环境");
        return false;
      }
      if (!deployMode) {
        message.warning("请选择部署方式");
        return false;
      }
    }
    if (step === 2 && !database) {
      message.warning("请选择数据库中间件");
      return false;
    }
    if (step === 3) {
      await form.validateFields(["env", "namespacePrefix", "domain"]);
    }
    return true;
  };

  const goNextExportStep = async () => {
    try {
      if (!(await validateExportStep())) return;
      setExportStep((current) => Math.min(current + 1, EXPORT_WIZARD_STEPS.length - 1));
    } catch (error) {
      if (error instanceof Error) message.error(error.message);
    }
  };

  const goPreviousExportStep = () => {
    setExportStep((current) => Math.max(current - 1, 0));
  };

  const openRegisterModal = () => {
    registerForm.setFieldsValue({
      sourceEnv,
      key: "",
      name: "",
      profile: "",
    });
    setRegisterModalOpen(true);
  };

  const submitBusinessRegistration = async () => {
    try {
      const values = await registerForm.validateFields();
      setRegisteringBusiness(true);
      await registerBusinessPlatform({
        sourceEnv: values.sourceEnv,
        key: values.key,
        name: values.name,
        profile: values.profile || "",
      });
      message.success("业务平台 namespace 已注册");
      setRegisterModalOpen(false);
      await loadOptions();
      void refreshAuditEvents();
    } catch (error) {
      if (error instanceof Error) message.error(error.message);
    } finally {
      setRegisteringBusiness(false);
    }
  };

  const disableBusiness = async (item: DeploymentServiceOption) => {
    if (!item.sourceEnv || !item.key) return;
    setDisablingBusinessKey(businessPlatformRowKey(item));
    try {
      await disableBusinessPlatform(item.sourceEnv as SourceEnv, item.key, item.profile || "");
      message.success("业务平台已注销");
      await loadOptions();
      void refreshAuditEvents();
    } catch (error) {
      message.error(error instanceof Error ? error.message : "业务平台注销失败");
    } finally {
      setDisablingBusinessKey("");
    }
  };

  const onRequiredPlatformClick = (event: CheckboxChangeEvent) => {
    if (!event.target.checked) message.info("必选基础能力会自动保留在部署包中");
  };

  const buildPackage = async () => {
    try {
      if (!(await validateExportStep(0))) return;
      if (!(await validateExportStep(2))) return;
      if (!(await validateExportStep(3))) return;
      const values = await form.validateFields();
      setBuilding(true);
      const payload = await createDeploymentPackage({
        ...makePreviewPayload(),
        imageMode: values.imageMode,
        targetProfile: {
          env: values.env,
          domain: values.domain,
          sourceRegistry: values.sourceRegistry || "",
          sourceRegistryInsecure: Boolean(values.sourceRegistryInsecure),
          registry: values.registry || "",
          namespacePrefix: values.namespacePrefix,
          storageClass: values.storageClass || "",
          exportImages: values.imageMode === "image-archive",
        },
      });
      setTask(payload);
      void refreshTasks();
      void refreshAuditEvents();
      message.success("部署任务已创建");
      setExportWizardOpen(false);
      setExportStep(0);
    } catch (error) {
      if (error instanceof Error) message.error(error.message);
    } finally {
      setBuilding(false);
    }
  };

  const cancelTask = async () => {
    if (!task) return;
    setTaskActionLoading(true);
    try {
      const payload = await cancelDeploymentPackageTask(task.taskId);
      setTask(payload);
      void refreshTasks();
      void refreshAuditEvents();
      message.success(payload.status === "canceled" ? "任务已取消" : "已请求取消任务");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "任务取消失败");
    } finally {
      setTaskActionLoading(false);
    }
  };

  const retryTask = async () => {
    if (!task) return;
    setTaskActionLoading(true);
    try {
      const payload = await retryDeploymentPackageTask(task.taskId);
      setTask(payload);
      void refreshTasks();
      void refreshAuditEvents();
      message.success("已创建重试任务");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "任务重试失败");
    } finally {
      setTaskActionLoading(false);
    }
  };

  const runCleanup = async (dryRun: boolean) => {
    setCleanupLoading(true);
    try {
      const payload = await cleanupDeploymentPackages(dryRun);
      setCleanupResult(payload);
      void refreshTasks();
      void refreshAuditEvents();
      if (task) void refreshSelectedTask(task.taskId);
      message.success(dryRun ? "清理预演完成" : "清理完成");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "部署包清理失败");
    } finally {
      setCleanupLoading(false);
    }
  };

  const downloadTaskArtifact = async () => {
    if (!task?.result || !task.artifactAvailable) return;
    setDownloadLoading(true);
    try {
      triggerBrowserDownload(downloadDeploymentPackage(task.result.packageId), `${task.result.packageId}.tar.gz`);
      void refreshAuditEvents();
    } catch (error) {
      message.error(error instanceof Error ? error.message : "部署包下载失败");
    } finally {
      setDownloadLoading(false);
    }
  };

  const downloadTaskChecksum = async () => {
    if (!task?.result || !task.artifactAvailable) return;
    setChecksumDownloadLoading(true);
    try {
      triggerBrowserDownload(downloadDeploymentPackageChecksum(task.result.packageId), `${task.result.packageId}.tar.gz.sha256`);
      void refreshAuditEvents();
    } catch (error) {
      message.error(error instanceof Error ? error.message : "校验文件下载失败");
    } finally {
      setChecksumDownloadLoading(false);
    }
  };

  useEffect(() => {
    if (!task || task.status === "completed" || task.status === "failed" || task.status === "canceled") return;
    const timer = window.setInterval(() => {
      void refreshSelectedTask(task.taskId)
        .then((payload) => {
          if (!payload) return;
          if (payload.status === "completed") message.success("部署包生成完成");
          if (payload.status === "failed") message.error(payload.error || "部署包生成失败");
          if (payload.status === "canceled") message.info("部署包任务已取消");
        });
    }, 1200);
    return () => window.clearInterval(timer);
  }, [message, refreshSelectedTask, task]);

  useEffect(() => {
    void refreshTasks();
    void refreshAuditEvents();
  }, [refreshAuditEvents, refreshTasks]);

  useEffect(() => {
    if (!tasks.some((item) => item.status === "pending" || item.status === "running")) return;
    const timer = window.setInterval(() => void refreshTasks(), 3000);
    return () => window.clearInterval(timer);
  }, [refreshTasks, tasks]);

  return (
    <section className={`panel ${styles.page}`}>
      <div className="panel-header">
        <div>
          <h2>部署包工厂</h2>
          <p>管理业务平台 namespace，并按真实环境镜像生成生产部署包</p>
        </div>
        <Space>
          <Button icon={<i className="ri-list-check-3" />} loading={tasksLoading} onClick={() => void refreshTasks()}>刷新任务</Button>
          <Button icon={<i className="ri-hard-drive-2-line" />} loading={imageEnvironmentLoading} onClick={() => void refreshImageEnvironment()}>检查镜像环境</Button>
          <Button icon={<i className="ri-refresh-line" />} loading={loadingOptions} onClick={() => void loadOptions()}>刷新选项</Button>
          <Button icon={<i className="ri-add-circle-line" />} onClick={openRegisterModal}>注册业务平台</Button>
          <Button type="primary" icon={<i className="ri-package-line" />} loading={building} onClick={openExportWizard}>创建导包任务</Button>
        </Space>
      </div>

      <div className="panel-body">
        <Tabs
          items={[
            {
              key: "platforms",
              label: "平台注册管理",
              children: (
                <PlatformRegistryPanel
                  options={options}
                  loading={loadingOptions}
                  registeredBusinessOptions={registeredBusinessOptions}
                  onRefresh={() => void loadOptions()}
                  onRegister={openRegisterModal}
                  onDisable={(item) => void disableBusiness(item)}
                  disablingBusinessKey={disablingBusinessKey}
                />
              ),
            },
            {
              key: "exports",
              label: "项目导出管理",
              children: (
                <div className={styles.content}>
                  <Spin spinning={loadingOptions}>
                    <div className={styles.exportLaunchPanel}>
                      <div className={styles.launchHeader}>
                        <span>
                          <i className="ri-guide-line" />
                        </span>
                        <div>
                          <h3>向导式导包</h3>
                          <p>按产品范围、平台能力、中间件、目标环境逐步确认，最后创建导包任务。</p>
                        </div>
                      </div>
                      <div className={styles.draftGrid}>
                        <DraftItem label="项目" value={selectedProject?.name || projectKey || "未选择"} />
                        <DraftItem label="版本" value={productVersion || "未选择"} />
                        <DraftItem label="来源" value={sourceEnv === "dev" ? "开发环境" : "测试环境"} />
                        <DraftItem label="部署" value={deployMode === "k8s" ? "Kubernetes" : "Docker Compose"} />
                        <DraftItem label="业务平台" value={`${selectedBusinessOptions.length} 个`} />
                        <DraftItem label="基础平台" value={`${selectedPlatformOptions.length} 个`} />
                        <DraftItem label="数据库" value={selectedDatabaseOption?.name || database || "未选择"} />
                        <DraftItem label="目标" value={`${targetDraft.namespacePrefix || "-"} / ${targetDraft.domain || "-"}`} />
                      </div>
                      <Space wrap>
                        <Button type="primary" icon={<i className="ri-compass-3-line" />} onClick={openExportWizard}>打开导包向导</Button>
                        <Button icon={<i className="ri-eye-line" />} loading={previewing} onClick={() => void refreshPreview()}>刷新预览</Button>
                        <Button icon={<i className="ri-node-tree" />} disabled={!preview} onClick={() => setExportDrawer("preview")}>查看依赖图</Button>
                      </Space>
                    </div>
                  </Spin>

                  <div className={styles.workspace}>
                    <div className={styles.previewPanel}>
                      <div className={styles.panelTitleRow}>
                        <h3 className={styles.sectionTitle}>依赖预览</h3>
                        <Space>
                          <Button size="small" icon={<i className="ri-eye-line" />} loading={previewing} onClick={() => void refreshPreview()}>预览</Button>
                          <Button size="small" icon={<i className="ri-node-tree" />} disabled={!preview} onClick={() => setExportDrawer("preview")}>详情</Button>
                        </Space>
                      </div>
                      {preview ? <PreviewSnapshot preview={preview} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无预览" />}
                    </div>

                    <TaskStatusPanel
                      task={task}
                      taskActionLoading={taskActionLoading}
                      downloadLoading={downloadLoading}
                      checksumDownloadLoading={checksumDownloadLoading}
                      onOpenDetail={() => setExportDrawer("task")}
                      onCancel={() => void cancelTask()}
                      onRetry={() => void retryTask()}
                      onDownloadChecksum={() => void downloadTaskChecksum()}
                      onDownloadArtifact={() => void downloadTaskArtifact()}
                    />

                    <div className={styles.toolGrid}>
                      <ActionTile
                        icon="ri-list-check-3"
                        title="最近任务"
                        value={`${tasks.length} 条`}
                        actionLabel="打开"
                        loading={tasksLoading}
                        onAction={() => setExportDrawer("tasks")}
                      />
                      <ActionTile
                        icon="ri-delete-bin-6-line"
                        title="产物清理"
                        value={cleanupResult ? `释放 ${formatBytes(cleanupResult.freedBytes)}` : "待预演"}
                        actionLabel="打开"
                        loading={cleanupLoading}
                        onAction={() => setExportDrawer("cleanup")}
                      />
                      <ActionTile
                        icon="ri-shield-check-line"
                        title="最近审计"
                        value={`${auditEvents.length} 条`}
                        actionLabel="打开"
                        loading={auditLoading}
                        onAction={() => setExportDrawer("audit")}
                      />
                    </div>
                  </div>
                </div>
              ),
            },
          ]}
        />
      </div>

      <Drawer
        title={exportDrawerTitle(exportDrawer)}
        open={Boolean(exportDrawer)}
        onClose={() => setExportDrawer(null)}
        width="min(1080px, 92vw)"
        destroyOnClose
      >
        {exportDrawer === "preview" && preview ? (
          <PreviewSummary preview={preview} project={selectedProject} targetProfile={targetDraft} />
        ) : null}
        {exportDrawer === "task" ? (
          <TaskDetailPanel
            task={task}
            taskActionLoading={taskActionLoading}
            downloadLoading={downloadLoading}
            checksumDownloadLoading={checksumDownloadLoading}
            onCancel={() => void cancelTask()}
            onRetry={() => void retryTask()}
            onDownloadChecksum={() => void downloadTaskChecksum()}
            onDownloadArtifact={() => void downloadTaskArtifact()}
          />
        ) : null}
        {exportDrawer === "tasks" ? (
          <TaskListPanel
            tasks={tasks}
            loading={tasksLoading}
            selectedTaskId={task?.taskId}
            onSelect={(item) => {
              setTask(item);
              setExportDrawer("task");
            }}
            onRefresh={() => void refreshTasks()}
          />
        ) : null}
        {exportDrawer === "cleanup" ? (
          <CleanupPanel
            result={cleanupResult}
            loading={cleanupLoading}
            onDryRun={() => void runCleanup(true)}
            onCleanup={() => void runCleanup(false)}
          />
        ) : null}
        {exportDrawer === "audit" ? (
          <AuditPanel
            events={auditEvents}
            loading={auditLoading}
            onRefresh={() => void refreshAuditEvents()}
          />
        ) : null}
      </Drawer>

      <DeploymentPackageWizardModal
        businessOptionsForSourceEnv={businessOptionsForSourceEnv}
        businessServices={businessServices}
        building={building}
        database={database}
        databaseOptionsForSourceEnv={databaseOptionsForSourceEnv}
        deployMode={deployMode}
        form={form}
        imageEnvironment={imageEnvironment}
        imageEnvironmentLoading={imageEnvironmentLoading}
        open={exportWizardOpen}
        options={options}
        platformOptionsForSourceEnv={platformOptionsForSourceEnv}
        platformServices={platformServices}
        preview={preview}
        previewing={previewing}
        productVersion={productVersion}
        projectKey={projectKey}
        selectedBusinessOptions={selectedBusinessOptions}
        selectedDatabaseOption={selectedDatabaseOption}
        selectedPlatformOptions={selectedPlatformOptions}
        selectedProject={selectedProject}
        sourceEnv={sourceEnv}
        step={exportStep}
        targetDraft={targetDraft}
        onBuild={() => void buildPackage()}
        onBusinessChange={onBusinessChange}
        onCancel={() => setExportWizardOpen(false)}
        onDatabaseChange={setDatabase}
        onDeployModeChange={setDeployMode}
        onNext={() => void goNextExportStep()}
        onPlatformChange={onPlatformChange}
        onPrevious={goPreviousExportStep}
        onProductVersionChange={setProductVersion}
        onProjectChange={applyProjectDefaults}
        onRefreshPreview={() => void refreshPreview()}
        onRequiredPlatformClick={onRequiredPlatformClick}
        onSourceEnvChange={setSourceEnv}
        onTargetDraftChange={setTargetDraft}
      />

      <BusinessPlatformRegistrationModal
        form={registerForm}
        loading={registeringBusiness}
        open={registerModalOpen}
        options={options}
        onCancel={() => setRegisterModalOpen(false)}
        onSubmit={() => void submitBusinessRegistration()}
      />
    </section>
  );
};

function PlatformRegistryPanel({
  options,
  loading,
  registeredBusinessOptions,
  onRefresh,
  onRegister,
  onDisable,
  disablingBusinessKey,
}: {
  options: DeploymentPackageOptions | null;
  loading: boolean;
  registeredBusinessOptions: DeploymentServiceOption[];
  onRefresh: () => void;
  onRegister: () => void;
  onDisable: (item: DeploymentServiceOption) => void;
  disablingBusinessKey: string;
}) {
  return (
    <div className={styles.registryLayout}>
      <div className={styles.resultPanel}>
        <div className={styles.panelTitleRow}>
          <div>
            <h3 className={styles.sectionTitle}>业务平台 namespace</h3>
            <span className={styles.muted}>业务平台按环境注册，一个环境下的业务平台对应一个 namespace。</span>
          </div>
          <Space>
            <Button icon={<i className="ri-refresh-line" />} loading={loading} onClick={onRefresh}>刷新</Button>
            <Button type="primary" icon={<i className="ri-add-circle-line" />} onClick={onRegister}>注册业务平台</Button>
          </Space>
        </div>
        {registeredBusinessOptions.length ? (
          <div className={styles.taskList}>
            {registeredBusinessOptions.map((item) => (
              <div key={`${item.sourceEnv}-${item.key}-${item.namespace}`} className={styles.taskItem}>
                <span className={styles.taskItemMain}>
                  <span>
                    <strong>{item.name}</strong>
                    <Tag color="blue" style={{ marginLeft: 8 }}>{item.sourceEnv}</Tag>
                    <Tag color="green">{item.status || "active"}</Tag>
                  </span>
                  <span className={styles.mono}>{item.namespace}</span>
                </span>
                <Popconfirm
                  title="注销业务平台？"
                  description="注销只会标记 namespace 停用，不会物理删除业务资源。"
                  onConfirm={() => onDisable(item)}
                >
                  <Button
                    danger
                    size="small"
                    icon={<i className="ri-forbid-line" />}
                    loading={disablingBusinessKey === businessPlatformRowKey(item)}
                  >
                    注销
                  </Button>
                </Popconfirm>
              </div>
            ))}
          </div>
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无已注册业务平台" />
        )}
      </div>
    </div>
  );
}

function PreviewSummary({ preview, project, targetProfile }: { preview: PackagePreview; project: ProjectProfile | null; targetProfile: TargetDraft }) {
  const imageEntries = preview.imageEntries ?? [];
  const groupedImageEntries = imageEntries.reduce<Record<string, typeof imageEntries>>((result, item) => {
    result[item.group] = result[item.group] || [];
    result[item.group].push(item);
    return result;
  }, {});
  return (
    <div className={styles.page}>
      <div className={styles.previewGrid}>
        <DependencyBlock title="基础平台" items={preview.platformServices} color="blue" />
        <DependencyBlock title="业务平台" items={preview.businessServices} color="purple" />
        <DependencyBlock title="中间件服务" items={preview.middleware} color="cyan" />
        <div className={styles.previewBlock}>
          <h3>数据库二选一</h3>
          <Tag color={preview.database.domestic ? "red" : "blue"}>{preview.database.name}</Tag>
          <div className={`${styles.mono} ${styles.imageList}`}>{preview.database.image}</div>
        </div>
      </div>
      <DependencyGraph preview={preview} />
      {preview.warnings.length ? (
        <div className={styles.previewBlock}>
          <h3>提示</h3>
          <div className={styles.tagList}>
            {preview.warnings.map((warning) => <Tag key={warning} color="warning">{warning}</Tag>)}
          </div>
        </div>
      ) : null}
      <div className={styles.previewBlock}>
        <h3>镜像清单</h3>
        <div className={styles.imageList}>
          {Object.entries(groupedImageEntries).map(([group, images]) => (
            <div className={styles.imageGroup} key={group}>
              <strong>{group}</strong>
              <div className={styles.imageMapList}>
                {images.map((image) => (
                  <div className={`${styles.imageMapRow} ${image.sourceMissing ? styles.imageMapRowMissing : ""}`} key={`${group}-${image.targetRef}`}>
                    <span className={styles.mono}>
                      {image.sourceRef}
                      {image.sourceResolvedFrom === "kubernetes" ? <Tag color="green" style={{ marginLeft: 6 }}>K8s</Tag> : null}
                      {image.sourceMissing ? <Tag color="red" style={{ marginLeft: 6 }}>未匹配</Tag> : null}
                      {image.sourceMessage ? <span className={styles.imageMessage}>{image.sourceMessage}</span> : null}
                    </span>
                    <i className="ri-arrow-right-line" />
                    <span className={styles.mono}>{image.targetRef}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className={styles.previewBlock}>
        <h3>项目 Overlay</h3>
        <div className={styles.summaryRow}>
          <span className={styles.muted}>输出目录</span>
          <span className={styles.mono}>overlays/{project?.key || "custom"}</span>
        </div>
        <div className={styles.summaryRow}>
          <span className={styles.muted}>产物</span>
          <span className={styles.mono}>values.json / kustomization.yaml / README.md</span>
        </div>
      </div>
    </div>
  );
}

function DependencyBlock({ title, items, color }: { title: string; items: PackagePreview["middleware"]; color: string }) {
  return (
    <div className={styles.previewBlock}>
      <h3>{title}</h3>
      <div className={styles.tagList}>
        {items.length ? items.map((item) => (
          <Tag key={item.key} color={item.locked ? color : "default"}>
            {item.name}
          </Tag>
        )) : <Tag>未选择</Tag>}
      </div>
    </div>
  );
}
