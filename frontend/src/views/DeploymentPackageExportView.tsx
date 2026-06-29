import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { App, Button, Checkbox, Drawer, Empty, Form, Input, Modal, Popconfirm, Progress, Radio, Select, Space, Spin, Steps, Tabs, Tag } from "antd";
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
import styles from "./DeploymentPackageExportView.module.css";

const DEFAULT_TARGET = {
  env: "prod",
  domain: "prod.example.com",
  sourceRegistry: "",
  sourceRegistryInsecure: false,
  registry: "",
  namespacePrefix: "prod",
  storageClass: "",
  exportImages: true,
};
type TargetDraft = typeof DEFAULT_TARGET & { imageMode?: "image-manifest" | "image-archive" };
const DEFAULT_IMAGE_MODE: TargetDraft["imageMode"] = "image-archive";
const EXPORT_WIZARD_STEPS = ["产品范围", "平台能力", "中间件与镜像", "目标环境", "确认导出"];
type PreviewDependencyItem = PackagePreview["middleware"][number];
type DependencyGraphNodeKind = "business" | "platform" | "middleware" | "database";
type DependencyGraphNode = {
  id: string;
  key: string;
  label: string;
  kind: DependencyGraphNodeKind;
  detail?: string;
  matchKeys: string[];
};
type DependencyGraphEdge = {
  from: string;
  to: string;
  kind: "platform" | "middleware";
};
type DependencyGraphModel = {
  businessNodes: DependencyGraphNode[];
  platformNodes: DependencyGraphNode[];
  middlewareNodes: DependencyGraphNode[];
  edges: DependencyGraphEdge[];
};
type ExportDrawerKey = "preview" | "task" | "tasks" | "cleanup" | "audit";

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

      <Modal
        title="创建部署包"
        open={exportWizardOpen}
        onCancel={() => setExportWizardOpen(false)}
        width="min(1040px, 94vw)"
        destroyOnClose={false}
        footer={(
          <div className={styles.wizardFooter}>
            <Button onClick={() => setExportWizardOpen(false)}>取消</Button>
            <Space>
              <Button disabled={exportStep === 0} onClick={goPreviousExportStep}>上一步</Button>
              {exportStep < EXPORT_WIZARD_STEPS.length - 1 ? (
                <Button type="primary" onClick={() => void goNextExportStep()}>下一步</Button>
              ) : (
                <Button type="primary" icon={<i className="ri-package-line" />} loading={building} onClick={() => void buildPackage()}>
                  创建导包任务
                </Button>
              )}
            </Space>
          </div>
        )}
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{ ...DEFAULT_TARGET, imageMode: DEFAULT_IMAGE_MODE }}
          onValuesChange={(_, values) => setTargetDraft((current) => ({ ...current, ...values }))}
        >
          <Steps
            className={styles.wizardSteps}
            size="small"
            current={exportStep}
            items={EXPORT_WIZARD_STEPS.map((title) => ({ title }))}
          />

          <div className={styles.wizardBody}>
            {exportStep === 0 ? (
              <div className={styles.wizardSection}>
                <h3 className={styles.sectionTitle}>产品范围</h3>
                <div className={styles.split}>
                  <Form.Item label="项目">
                    <Select
                      value={projectKey}
                      options={(options?.projects ?? []).map((item) => ({ value: item.key, label: item.name }))}
                      onChange={(value) => applyProjectDefaults(value)}
                      placeholder="暂无真实项目"
                      disabled={!options?.projects.length}
                    />
                  </Form.Item>
                  <Form.Item label="产品版本">
                    <Select
                      value={productVersion}
                      options={(options?.projects.find((item) => item.key === projectKey)?.versions ?? []).map((item) => ({ value: item, label: item }))}
                      onChange={(value) => setProductVersion(value)}
                      placeholder="暂无真实版本"
                      disabled={!(options?.projects.find((item) => item.key === projectKey)?.versions ?? []).length}
                    />
                  </Form.Item>
                </div>
                <ProjectSummary project={selectedProject} />
                <div className={styles.split}>
                  <Form.Item label="来源环境">
                    <Radio.Group value={sourceEnv} onChange={(event) => setSourceEnv(event.target.value)}>
                      {(options?.sourceEnvs ?? []).map((env) => (
                        <Radio.Button key={env} value={env}>{env === "dev" ? "开发环境" : "测试环境"}</Radio.Button>
                      ))}
                    </Radio.Group>
                    {options?.sourceEnvs.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无可读取的来源环境" /> : null}
                  </Form.Item>
                  <Form.Item label="部署方式">
                    <Radio.Group value={deployMode} onChange={(event) => setDeployMode(event.target.value)}>
                      <Space direction="vertical">
                        {(options?.deployModes ?? ["k8s", "docker-compose"]).map((mode) => (
                          <Radio key={mode} value={mode}>{mode === "k8s" ? "Kubernetes" : "Docker Compose"}</Radio>
                        ))}
                      </Space>
                    </Radio.Group>
                  </Form.Item>
                </div>
              </div>
            ) : null}

            {exportStep === 1 ? (
              <div className={styles.wizardGrid}>
                <div className={styles.wizardSection}>
                  <h3 className={styles.sectionTitle}>业务平台服务</h3>
                  <Checkbox.Group className={styles.serviceGrid} value={businessServices} onChange={onBusinessChange}>
                    {businessOptionsForSourceEnv.map((item) => (
                      <Checkbox key={`${item.sourceEnv}-${item.key}-${item.profile || "default"}`} value={businessOptionValue(item)}>
                        <span className={styles.serviceItem}>
                          <span className={styles.serviceMain}>
                            <i className="ri-apps-2-line" />
                            <span className={styles.serviceName}>{item.name}</span>
                          </span>
                          <span className={styles.muted}>{item.namespace || item.profile || item.namespaceGroup}</span>
                        </span>
                      </Checkbox>
                    ))}
                  </Checkbox.Group>
                  {businessOptionsForSourceEnv.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前来源环境暂无已注册业务平台" /> : null}
                </div>
                <div className={styles.wizardSection}>
                  <h3 className={styles.sectionTitle}>基础平台服务</h3>
                  <Checkbox.Group className={styles.serviceGrid} value={platformServices} onChange={onPlatformChange}>
                    {platformOptionsForSourceEnv.map((item) => (
                      <Checkbox key={item.key} value={item.key} disabled={item.required} onChange={item.required ? onRequiredPlatformClick : undefined}>
                        <span className={styles.serviceItem}>
                          <span className={styles.serviceMain}>
                            <i className="ri-server-line" />
                            <span className={styles.serviceName}>{item.name}</span>
                          </span>
                          <span className={styles.muted}>{item.required ? "必选" : item.namespaceGroup}</span>
                        </span>
                      </Checkbox>
                    ))}
                  </Checkbox.Group>
                  {platformOptionsForSourceEnv.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前来源环境暂无真实基础平台服务" /> : null}
                </div>
              </div>
            ) : null}

            {exportStep === 2 ? (
              <div className={styles.wizardGrid}>
                <div className={styles.wizardSection}>
                  <h3 className={styles.sectionTitle}>中间件服务</h3>
                  <Form.Item label="数据库中间件（二选一）">
                    <Radio.Group value={database} onChange={(event) => setDatabase(event.target.value)}>
                      <Space direction="vertical">
                        {databaseOptionsForSourceEnv.map((item) => (
                          <Radio key={item.key} value={item.key}>
                            {item.name}
                            <Tag color={item.domestic ? "red" : "blue"} style={{ marginLeft: 8 }}>{item.domestic ? "国产化" : "非国产化"}</Tag>
                          </Radio>
                        ))}
                      </Space>
                    </Radio.Group>
                    {databaseOptionsForSourceEnv.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前来源环境暂无真实数据库服务" /> : null}
                  </Form.Item>
                </div>
                <div className={styles.wizardSection}>
                  <h3 className={styles.sectionTitle}>镜像导出</h3>
                  <Form.Item label="镜像模式" name="imageMode">
                    <Select
                      options={[
                        { value: "image-archive", label: "镜像归档：导出离线镜像 tar" },
                        { value: "image-manifest", label: "镜像清单：仅生成 pull/save/load 脚本" },
                      ]}
                    />
                  </Form.Item>
                  <ImageEnvironmentStatus value={imageEnvironment} loading={imageEnvironmentLoading} />
                </div>
              </div>
            ) : null}

            {exportStep === 3 ? (
              <div className={styles.wizardSection}>
                <h3 className={styles.sectionTitle}>生产目标</h3>
                <div className={styles.split}>
                  <Form.Item label="目标环境" name="env" rules={[{ required: true, message: "请输入目标环境" }]}>
                    <Input />
                  </Form.Item>
                  <Form.Item label="命名空间前缀" name="namespacePrefix" rules={[{ required: true, message: "请输入命名空间前缀" }]}>
                    <Input />
                  </Form.Item>
                  <Form.Item label="域名" name="domain" rules={[{ required: true, message: "请输入生产域名" }]}>
                    <Input />
                  </Form.Item>
                  <Form.Item label="源镜像仓库" name="sourceRegistry">
                    <Input placeholder="可选，导包时从该仓库拉取镜像" />
                  </Form.Item>
                  <Form.Item name="sourceRegistryInsecure" valuePropName="checked">
                    <Checkbox>源仓库使用自签证书</Checkbox>
                  </Form.Item>
                  <Form.Item label="镜像仓库" name="registry">
                    <Input placeholder="生产部署目标镜像仓库" />
                  </Form.Item>
                  <Form.Item label="StorageClass" name="storageClass">
                    <Input placeholder="留空使用集群默认值" />
                  </Form.Item>
                </div>
              </div>
            ) : null}

            {exportStep === 4 ? (
              <div className={styles.wizardGrid}>
                <div className={styles.wizardSection}>
                  <h3 className={styles.sectionTitle}>导包确认</h3>
                  <div className={styles.draftGrid}>
                    <DraftItem label="项目" value={selectedProject?.name || projectKey || "未选择"} />
                    <DraftItem label="版本" value={productVersion || "未选择"} />
                    <DraftItem label="来源环境" value={sourceEnv === "dev" ? "开发环境" : "测试环境"} />
                    <DraftItem label="部署方式" value={deployMode === "k8s" ? "Kubernetes" : "Docker Compose"} />
                    <DraftItem label="业务平台" value={selectedBusinessOptions.map((item) => item.name).join("、") || "未选择"} />
                    <DraftItem label="基础平台" value={selectedPlatformOptions.map((item) => item.name).join("、") || "未选择"} />
                    <DraftItem label="数据库" value={selectedDatabaseOption?.name || database || "未选择"} />
                    <DraftItem label="镜像模式" value={targetDraft.imageMode === "image-manifest" ? "镜像清单" : "镜像归档"} />
                    <DraftItem label="目标环境" value={targetDraft.env || "-"} />
                    <DraftItem label="目标域名" value={targetDraft.domain || "-"} />
                    <DraftItem label="命名空间" value={targetDraft.namespacePrefix || "-"} />
                    <DraftItem label="StorageClass" value={targetDraft.storageClass || "集群默认"} />
                  </div>
                </div>
                <div className={styles.wizardSection}>
                  <div className={styles.panelTitleRow}>
                    <h3 className={styles.sectionTitle}>预览摘要</h3>
                    <Button size="small" icon={<i className="ri-refresh-line" />} loading={previewing} onClick={() => void refreshPreview()}>刷新</Button>
                  </div>
                  {preview ? <PreviewSnapshot preview={preview} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无预览" />}
                </div>
              </div>
            ) : null}
          </div>
        </Form>
      </Modal>

      <Modal
        title="注册业务平台"
        open={registerModalOpen}
        onCancel={() => setRegisterModalOpen(false)}
        onOk={() => void submitBusinessRegistration()}
        confirmLoading={registeringBusiness}
        okText="注册 namespace"
        cancelText="取消"
      >
        <Form form={registerForm} layout="vertical">
          <Form.Item label="环境" name="sourceEnv" rules={[{ required: true, message: "请选择环境" }]}>
            <Radio.Group>
              {(options?.sourceEnvs ?? ["dev", "test"]).map((env) => (
                <Radio.Button key={env} value={env}>{env === "dev" ? "开发环境" : "测试环境"}</Radio.Button>
              ))}
            </Radio.Group>
          </Form.Item>
          <div className={styles.split}>
            <Form.Item label="业务 Key" name="key" rules={[{ required: true, message: "请输入业务 Key" }]}>
              <Input placeholder="eam / mes / erp" />
            </Form.Item>
            <Form.Item label="业务名称" name="name" rules={[{ required: true, message: "请输入业务名称" }]}>
              <Input placeholder="EAM" />
            </Form.Item>
          </div>
          <Form.Item label="部署规格" name="profile">
            <Input placeholder="4x60 / 4x3，可选" />
          </Form.Item>
        </Form>
      </Modal>
    </section>
  );
};

function DraftItem({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className={styles.draftItem}>
      <span className={styles.muted}>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function ProjectSummary({ project }: { project: ProjectProfile | null }) {
  if (!project) {
    return (
      <div className={styles.projectSummary}>
        <span className={styles.muted}>未选择项目模板</span>
      </div>
    );
  }
  return (
    <div className={styles.projectSummary}>
      <div className={styles.summaryRow}>
        <span className={styles.muted}>镜像 Tag</span>
        <Tag color="geekblue">{project.imageTag || "prod"}</Tag>
      </div>
      <div className={styles.summaryRow}>
        <span className={styles.muted}>Overlay</span>
        <div className={styles.tagList}>
          {project.overlays.length ? project.overlays.map((item) => <Tag key={item}>{item}</Tag>) : <Tag>默认</Tag>}
        </div>
      </div>
      <div className={styles.summaryRow}>
        <span className={styles.muted}>目标配置</span>
        <span className={styles.mono}>{project.namespacePrefix} / {project.domain} / {project.storageClass || "default-storage"}</span>
      </div>
    </div>
  );
}

function ImageEnvironmentStatus({ value, loading }: { value: ImageExportEnvironmentCheck | null; loading: boolean }) {
  const color = value?.available ? "green" : "orange";
  const label = value?.available ? "导出工具可用" : "导出工具不可用";
  return (
    <div className={styles.imageEnvironment}>
      <Space size={8} wrap>
        <Tag color={loading ? "processing" : color}>{loading ? "检查中" : label}</Tag>
        {value?.exportTool ? <Tag>{value.exportTool}</Tag> : null}
        {value?.toolVersion || value?.dockerVersion ? <span className={styles.mono}>{value.toolVersion || value.dockerVersion}</span> : null}
      </Space>
      <span className={styles.muted}>
        {value?.message || "镜像归档模式需要导包 worker 可访问镜像仓库，并具备 skopeo 或 Docker CLI 导出能力。"}
      </span>
    </div>
  );
}

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

function ValidationSummary({ result }: { result: NonNullable<PackageTask["result"]> }) {
  const summary = result.validationSummary || {};
  const artifactSize = summary.artifactSize || result.artifactSize || 0;
  return (
    <div className={styles.validationSummary}>
      <div className={styles.metricItem}>
        <span className={styles.muted}>包大小</span>
        <strong>{formatBytes(artifactSize)}</strong>
      </div>
      <div className={styles.metricItem}>
        <span className={styles.muted}>索引文件</span>
        <strong>{summary.packageIndexFileCount ?? 0}</strong>
      </div>
      <div className={styles.metricItem}>
        <span className={styles.muted}>镜像条目</span>
        <strong>{summary.imageEntryCount ?? 0}</strong>
      </div>
      <div className={styles.metricItem}>
        <span className={styles.muted}>镜像归档</span>
        <strong>{summary.imageArchiveCount ?? 0}</strong>
      </div>
      <div className={styles.metricItem}>
        <span className={styles.muted}>缺失归档</span>
        <strong>{summary.missingImageArchiveCount ?? 0}</strong>
      </div>
    </div>
  );
}

function PreviewSnapshot({ preview }: { preview: PackagePreview }) {
  const missingImages = (preview.imageEntries ?? []).filter((item) => item.sourceMissing).length;
  return (
    <div className={styles.snapshotGrid}>
      <div className={styles.metricItem}>
        <span className={styles.muted}>基础平台</span>
        <strong>{preview.platformServices.length}</strong>
      </div>
      <div className={styles.metricItem}>
        <span className={styles.muted}>业务平台</span>
        <strong>{preview.businessServices.length}</strong>
      </div>
      <div className={styles.metricItem}>
        <span className={styles.muted}>中间件</span>
        <strong>{preview.middleware.length}</strong>
      </div>
      <div className={styles.metricItem}>
        <span className={styles.muted}>镜像条目</span>
        <strong>{preview.imageEntries.length}</strong>
      </div>
      <div className={styles.summaryRow}>
        <span className={styles.muted}>数据库</span>
        <Space size={6} wrap>
          <Tag color={preview.database.domestic ? "red" : "blue"}>{preview.database.name}</Tag>
          {missingImages ? <Tag color="red">{missingImages} 个镜像未匹配</Tag> : <Tag color="green">镜像已匹配</Tag>}
        </Space>
      </div>
    </div>
  );
}

function TaskStatusPanel({
  task,
  taskActionLoading,
  downloadLoading,
  checksumDownloadLoading,
  onOpenDetail,
  onCancel,
  onRetry,
  onDownloadChecksum,
  onDownloadArtifact,
}: {
  task: PackageTask | null;
  taskActionLoading: boolean;
  downloadLoading: boolean;
  checksumDownloadLoading: boolean;
  onOpenDetail: () => void;
  onCancel: () => void;
  onRetry: () => void;
  onDownloadChecksum: () => void;
  onDownloadArtifact: () => void;
}) {
  return (
    <div className={styles.resultPanel}>
      <div className={styles.panelTitleRow}>
        <h3 className={styles.sectionTitle}>当前任务</h3>
        <Button size="small" icon={<i className="ri-file-list-3-line" />} disabled={!task} onClick={onOpenDetail}>详情</Button>
      </div>
      {task ? (
        <>
          <div className={styles.resultRow}>
            <span className={styles.muted}>任务 ID</span>
            <span className={styles.mono}>{task.taskId}</span>
          </div>
          <div className={styles.resultRow}>
            <span className={styles.muted}>状态</span>
            <Space size={6} wrap>
              <Tag color={taskStatusColor(task.status)}>{task.status}</Tag>
              <span>{task.message}</span>
            </Space>
          </div>
          <Progress percent={task.progress} status={task.status === "failed" ? "exception" : task.status === "completed" ? "success" : "active"} />
          {task.result ? <ValidationSummary result={task.result} /> : null}
          <TaskActions
            task={task}
            taskActionLoading={taskActionLoading}
            downloadLoading={downloadLoading}
            checksumDownloadLoading={checksumDownloadLoading}
            onCancel={onCancel}
            onRetry={onRetry}
            onDownloadChecksum={onDownloadChecksum}
            onDownloadArtifact={onDownloadArtifact}
          />
        </>
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无任务" />
      )}
    </div>
  );
}

function TaskDetailPanel({
  task,
  taskActionLoading,
  downloadLoading,
  checksumDownloadLoading,
  onCancel,
  onRetry,
  onDownloadChecksum,
  onDownloadArtifact,
}: {
  task: PackageTask | null;
  taskActionLoading: boolean;
  downloadLoading: boolean;
  checksumDownloadLoading: boolean;
  onCancel: () => void;
  onRetry: () => void;
  onDownloadChecksum: () => void;
  onDownloadArtifact: () => void;
}) {
  if (!task) return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="请选择任务" />;
  return (
    <div className={styles.resultPanel}>
      <div className={styles.resultRow}>
        <span className={styles.muted}>任务 ID</span>
        <span className={styles.mono}>{task.taskId}</span>
      </div>
      <div className={styles.resultRow}>
        <span className={styles.muted}>状态</span>
        <Space size={6} wrap>
          <Tag color={taskStatusColor(task.status)}>{task.status}</Tag>
          <span>{task.message}</span>
        </Space>
      </div>
      <Progress percent={task.progress} status={task.status === "failed" ? "exception" : task.status === "completed" ? "success" : "active"} />
      {task.result ? (
        <>
          <div className={styles.resultRow}>
            <span className={styles.muted}>包 ID</span>
            <span className={styles.mono}>{task.result.packageId}</span>
          </div>
          <div className={styles.resultRow}>
            <span className={styles.muted}>SHA256</span>
            <span className={styles.mono}>{task.result.sha256}</span>
          </div>
          <ValidationSummary result={task.result} />
          <div className={styles.resultRow}>
            <span className={styles.muted}>产物路径</span>
            <Space direction="vertical" size={4}>
              <span className={styles.mono}>{task.result.artifactPath}</span>
              {task.result.checksumPath ? <span className={styles.mono}>{task.result.checksumPath}</span> : null}
              <Tag color={task.artifactAvailable ? "green" : "default"}>{task.artifactAvailable ? "可下载" : "产物已清理"}</Tag>
            </Space>
          </div>
        </>
      ) : null}
      {task.error ? (
        <div className={styles.resultRow}>
          <span className={styles.muted}>错误</span>
          <span className={styles.mono}>{task.error}</span>
        </div>
      ) : null}
      <div className={styles.resultRow}>
        <span className={styles.muted}>日志</span>
        <div className={styles.logBox}>
          {task.logs.map((item, index) => (
            <div key={`${index}-${item}`} className={styles.mono}>{item}</div>
          ))}
        </div>
      </div>
      <TaskActions
        task={task}
        taskActionLoading={taskActionLoading}
        downloadLoading={downloadLoading}
        checksumDownloadLoading={checksumDownloadLoading}
        onCancel={onCancel}
        onRetry={onRetry}
        onDownloadChecksum={onDownloadChecksum}
        onDownloadArtifact={onDownloadArtifact}
      />
    </div>
  );
}

function TaskActions({
  task,
  taskActionLoading,
  downloadLoading,
  checksumDownloadLoading,
  onCancel,
  onRetry,
  onDownloadChecksum,
  onDownloadArtifact,
}: {
  task: PackageTask;
  taskActionLoading: boolean;
  downloadLoading: boolean;
  checksumDownloadLoading: boolean;
  onCancel: () => void;
  onRetry: () => void;
  onDownloadChecksum: () => void;
  onDownloadArtifact: () => void;
}) {
  return (
    <div className={styles.actions}>
      <Button
        icon={<i className="ri-close-circle-line" />}
        loading={taskActionLoading}
        disabled={task.status !== "pending" && task.status !== "running"}
        onClick={onCancel}
      >
        取消任务
      </Button>
      <Button
        icon={<i className="ri-restart-line" />}
        loading={taskActionLoading}
        disabled={task.status !== "failed" && task.status !== "canceled"}
        onClick={onRetry}
      >
        重试任务
      </Button>
      <Button
        icon={<i className="ri-file-shield-2-line" />}
        loading={checksumDownloadLoading}
        onClick={onDownloadChecksum}
        disabled={!task.result || !task.artifactAvailable}
      >
        下载校验文件
      </Button>
      <Button
        type="primary"
        icon={<i className="ri-download-line" />}
        loading={downloadLoading}
        onClick={onDownloadArtifact}
        disabled={!task.result || !task.artifactAvailable}
      >
        {task.result && !task.artifactAvailable ? "产物已清理" : "下载部署包"}
      </Button>
    </div>
  );
}

function ActionTile({
  icon,
  title,
  value,
  actionLabel,
  loading,
  onAction,
}: {
  icon: string;
  title: string;
  value: string;
  actionLabel: string;
  loading: boolean;
  onAction: () => void;
}) {
  return (
    <div className={styles.actionTile}>
      <i className={icon} />
      <span>
        <strong>{title}</strong>
        <span className={styles.muted}>{value}</span>
      </span>
      <Button size="small" loading={loading} onClick={onAction}>{actionLabel}</Button>
    </div>
  );
}

function AuditPanel({
  events,
  loading,
  onRefresh,
}: {
  events: AuditEvent[];
  loading: boolean;
  onRefresh: () => void;
}) {
  return (
    <div className={styles.resultPanel}>
      <div className={styles.panelTitleRow}>
        <h3 className={styles.sectionTitle}>最近审计</h3>
        <Button size="small" icon={<i className="ri-shield-check-line" />} loading={loading} onClick={onRefresh}>刷新</Button>
      </div>
      {events.length ? (
        <div className={styles.taskList}>
          {events.map((event) => (
            <div key={event.eventId} className={styles.taskItem}>
              <span className={styles.taskItemMain}>
                <span className={styles.mono}>{event.action}</span>
                <span className={styles.muted}>{event.message || event.targetId || event.createdAt}</span>
              </span>
              <Space size={4}>
                {event.operator ? <Tag>{event.operator}</Tag> : null}
                <Tag color={auditStatusColor(event.status)}>{event.status}</Tag>
              </Space>
            </div>
          ))}
        </div>
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无审计日志" />
      )}
    </div>
  );
}

function TaskListPanel({
  tasks,
  loading,
  selectedTaskId,
  onSelect,
  onRefresh,
}: {
  tasks: PackageTask[];
  loading: boolean;
  selectedTaskId?: string;
  onSelect: (task: PackageTask) => void;
  onRefresh: () => void;
}) {
  return (
    <div className={styles.resultPanel}>
      <div className={styles.panelTitleRow}>
        <h3 className={styles.sectionTitle}>最近任务</h3>
        <Button size="small" icon={<i className="ri-refresh-line" />} loading={loading} onClick={onRefresh}>刷新</Button>
      </div>
      {tasks.length ? (
        <div className={styles.taskList}>
          {tasks.map((item) => (
            <button
              key={item.taskId}
              type="button"
              className={`${styles.taskItem} ${item.taskId === selectedTaskId ? styles.taskItemActive : ""}`}
              onClick={() => onSelect(item)}
            >
              <span className={styles.taskItemMain}>
                <span className={styles.mono}>{item.result?.packageId || item.taskId}</span>
                <span className={styles.muted}>{item.message || item.updatedAt}</span>
              </span>
              <Space size={4}>
                {item.result && !item.artifactAvailable ? <Tag>已清理</Tag> : null}
                <Tag color={taskStatusColor(item.status)}>{item.status}</Tag>
              </Space>
            </button>
          ))}
        </div>
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无任务" />
      )}
    </div>
  );
}

function CleanupPanel({
  result,
  loading,
  onDryRun,
  onCleanup,
}: {
  result: CleanupResult | null;
  loading: boolean;
  onDryRun: () => void;
  onCleanup: () => void;
}) {
  return (
    <div className={styles.resultPanel}>
      <div className={styles.panelTitleRow}>
        <h3 className={styles.sectionTitle}>产物清理</h3>
        <Space>
          <Button size="small" icon={<i className="ri-search-eye-line" />} loading={loading} onClick={onDryRun}>预演</Button>
          <Popconfirm title="确认清理部署包产物？" description="任务记录会保留，已清理的包不能继续下载。" onConfirm={onCleanup}>
            <Button size="small" danger icon={<i className="ri-delete-bin-line" />} loading={loading}>清理</Button>
          </Popconfirm>
        </Space>
      </div>
      {result ? (
        <div className={styles.cleanupSummary}>
          <div className={styles.metricItem}>
            <span className={styles.muted}>扫描任务</span>
            <strong>{result.scannedTasks}</strong>
          </div>
          <div className={styles.metricItem}>
            <span className={styles.muted}>产物</span>
            <strong>{result.deletedArtifacts}</strong>
          </div>
          <div className={styles.metricItem}>
            <span className={styles.muted}>临时目录</span>
            <strong>{result.deletedWorkDirs}</strong>
          </div>
          <div className={styles.metricItem}>
            <span className={styles.muted}>释放</span>
            <strong>{formatBytes(result.freedBytes)}</strong>
          </div>
          <div className={styles.resultRow}>
            <span className={styles.muted}>模式</span>
            <Tag color={result.dryRun ? "blue" : "green"}>{result.dryRun ? "dry-run" : "executed"}</Tag>
          </div>
          <div className={styles.resultRow}>
            <span className={styles.muted}>路径</span>
            <div className={styles.logBox}>
              {result.deletedPaths.length ? result.deletedPaths.slice(0, 20).map((item) => (
                <div key={item} className={styles.mono}>{item}</div>
              )) : <span className={styles.muted}>没有需要清理的产物</span>}
            </div>
          </div>
        </div>
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="先执行清理预演" />
      )}
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

function DependencyGraph({ preview }: { preview: PackagePreview }) {
  const graph = useMemo(() => buildDependencyGraph(preview), [preview]);
  const sideBoxWidth = 330;
  const sideNodeWidth = 280;
  const bottomNodeWidth = 228;
  const nodeHeight = 48;
  const sideGap = 12;
  const bottomGap = 14;
  const framePadding = 16;
  const topY = 24;
  const frameTitleHeight = 38;
  const sideRows = Math.max(1, graph.platformNodes.length, graph.businessNodes.length);
  const bottomNodeCount = Math.max(1, graph.middlewareNodes.length);
  const bottomWidth = bottomNodeCount * bottomNodeWidth + (bottomNodeCount - 1) * bottomGap;
  const graphWidth = Math.max(1080, bottomWidth + framePadding * 2, sideBoxWidth * 2 + 260);
  const rightBoxX = graphWidth - sideBoxWidth;
  const sideNodeStartY = topY + frameTitleHeight;
  const sideBoxHeight = Math.max(260, frameTitleHeight + sideRows * (nodeHeight + sideGap) - sideGap + framePadding);
  const bottomBoxY = topY + sideBoxHeight + 42;
  const bottomBoxHeight = Math.max(126, frameTitleHeight + nodeHeight + framePadding);
  const bottomY = bottomBoxY + frameTitleHeight;
  const bottomStartX = Math.max(framePadding, (graphWidth - bottomWidth) / 2);
  const graphHeight = bottomBoxY + bottomBoxHeight + 16;
  const nodePositions = new Map<string, { x: number; y: number; width: number; height: number; lane: "platform" | "business" | "middleware" }>();
  graph.platformNodes.forEach((node, index) => nodePositions.set(node.id, { x: framePadding, y: sideNodeStartY + index * (nodeHeight + sideGap), width: sideNodeWidth, height: nodeHeight, lane: "platform" }));
  graph.businessNodes.forEach((node, index) => nodePositions.set(node.id, { x: rightBoxX + sideBoxWidth - framePadding - sideNodeWidth, y: sideNodeStartY + index * (nodeHeight + sideGap), width: sideNodeWidth, height: nodeHeight, lane: "business" }));
  graph.middlewareNodes.forEach((node, index) => nodePositions.set(node.id, { x: bottomStartX + index * (bottomNodeWidth + bottomGap), y: bottomY, width: bottomNodeWidth, height: nodeHeight, lane: "middleware" }));
  const nodes = [
    ...graph.platformNodes.map((node) => ({ node, position: nodePositions.get(node.id) })),
    ...graph.businessNodes.map((node) => ({ node, position: nodePositions.get(node.id) })),
    ...graph.middlewareNodes.map((node) => ({ node, position: nodePositions.get(node.id) })),
  ];
  const edgePath = (edge: DependencyGraphEdge) => {
    const from = nodePositions.get(edge.from);
    const to = nodePositions.get(edge.to);
    if (!from || !to) return "";
    const fromCenterX = from.x + from.width / 2;
    const fromCenterY = from.y + from.height / 2;
    const toCenterX = to.x + to.width / 2;
    const toCenterY = to.y + to.height / 2;
    if (from.lane === to.lane) {
      const outsideX = from.lane === "business" ? from.x - 26 : from.x + from.width + 26;
      const startX = from.lane === "business" ? from.x : from.x + from.width;
      const endX = startX;
      return `M ${startX} ${fromCenterY} C ${outsideX} ${fromCenterY}, ${outsideX} ${toCenterY}, ${endX} ${toCenterY}`;
    }
    if (to.lane === "middleware") {
      const startY = from.y + from.height;
      return `M ${fromCenterX} ${startY} C ${fromCenterX} ${startY + 42}, ${toCenterX} ${to.y - 42}, ${toCenterX} ${to.y}`;
    }
    const fromX = from.x < to.x ? from.x + from.width : from.x;
    const toX = from.x < to.x ? to.x : to.x + to.width;
    const direction = fromX < toX ? 1 : -1;
    const curve = Math.max(80, Math.abs(toX - fromX) / 2);
    return `M ${fromX} ${fromCenterY} C ${fromX + direction * curve} ${fromCenterY}, ${toX - direction * curve} ${toCenterY}, ${toX} ${toCenterY}`;
  };
  return (
    <div className={`${styles.previewBlock} ${styles.dependencyGraphBlock}`}>
      <div className={styles.graphHeader}>
        <h3>依赖关系图</h3>
        <div className={styles.graphLegend}>
          <span><i className={styles.graphLegendBusiness} />业务</span>
          <span><i className={styles.graphLegendPlatform} />平台</span>
          <span><i className={styles.graphLegendMiddleware} />中间件</span>
          <span><i className={styles.graphLegendDatabase} />数据库</span>
        </div>
      </div>
      <div className={styles.graphScroller}>
        <div className={styles.graphCanvas} style={{ width: graphWidth, height: graphHeight }}>
          <div className={styles.graphRegion} style={{ left: 0, top: topY, width: sideBoxWidth, height: sideBoxHeight }}>
            <span>基础平台</span>
          </div>
          <div className={styles.graphRegion} style={{ left: rightBoxX, top: topY, width: sideBoxWidth, height: sideBoxHeight }}>
            <span>业务平台</span>
          </div>
          <div className={`${styles.graphRegion} ${styles.graphRegionMiddleware}`} style={{ left: 0, top: bottomBoxY, width: graphWidth, height: bottomBoxHeight }}>
            <span>中间件 / 数据库</span>
          </div>
          {graph.edges.length ? (
            <svg className={styles.graphEdges} viewBox={`0 0 ${graphWidth} ${graphHeight}`} preserveAspectRatio="none" aria-hidden="true">
              <defs>
                <marker id="dependencyGraphArrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                  <path d="M 0 0 L 10 5 L 0 10 z" />
                </marker>
              </defs>
              {graph.edges.map((edge) => (
                <path
                  key={`${edge.from}-${edge.to}`}
                  className={edge.kind === "platform" ? styles.graphEdgePlatform : styles.graphEdgeMiddleware}
                  d={edgePath(edge)}
                  markerEnd="url(#dependencyGraphArrow)"
                />
              ))}
            </svg>
          ) : null}
          {nodes.map(({ node, position }) => position ? (
            <div
              className={styles.graphNodeSlot}
              key={node.id}
              style={{ left: position.x, top: position.y, width: position.width, height: position.height }}
            >
              <DependencyGraphNodeView node={node} />
            </div>
          ) : null)}
          {graph.platformNodes.length ? null : <div className={styles.graphEmptySlot} style={{ left: framePadding, top: sideNodeStartY, width: sideNodeWidth, height: nodeHeight }}>未选择</div>}
          {graph.businessNodes.length ? null : <div className={styles.graphEmptySlot} style={{ left: rightBoxX + sideBoxWidth - framePadding - sideNodeWidth, top: sideNodeStartY, width: sideNodeWidth, height: nodeHeight }}>未选择</div>}
          {graph.middlewareNodes.length ? null : <div className={styles.graphEmptySlot} style={{ left: bottomStartX, top: bottomY, width: bottomNodeWidth, height: nodeHeight }}>未选择</div>}
        </div>
      </div>
    </div>
  );
}

function DependencyGraphNodeView({ node }: { node: DependencyGraphNode }) {
  const className = `${styles.graphNode} ${graphNodeClassName(node.kind)}`;
  return (
    <div className={className} title={node.detail || node.label}>
      <i className={graphNodeIcon(node.kind)} />
      <span className={styles.graphNodeText}>
        <strong>{node.label}</strong>
        <span>{node.detail || node.key}</span>
      </span>
    </div>
  );
}

function buildDependencyGraph(preview: PackagePreview): DependencyGraphModel {
  const businessNodes = runtimeGraphNodes(preview, "business", "business", preview.businessServices);
  const platformNodes = runtimeGraphNodes(preview, "platform", "platform", preview.platformServices);
  const middlewareNodes = runtimeGraphNodes(preview, "middleware", "middleware", preview.middleware);
  const sourceNodeIdsByKey = new Map<string, string[]>();
  const platformNodeIdsByKey = new Map<string, string>();
  const middlewareNodeIdsByKey = new Map<string, string[]>();
  const addSourceNode = (node: DependencyGraphNode) => {
    node.matchKeys.forEach((matchKey) => {
      const nodes = sourceNodeIdsByKey.get(matchKey) ?? [];
      nodes.push(node.id);
      sourceNodeIdsByKey.set(matchKey, nodes);
    });
  };
  businessNodes.forEach(addSourceNode);
  platformNodes.forEach((node) => {
    addSourceNode(node);
    node.matchKeys.forEach((matchKey) => platformNodeIdsByKey.set(matchKey, node.id));
  });
  middlewareNodes.forEach((node) => {
    node.matchKeys.forEach((matchKey) => {
      const nodes = middlewareNodeIdsByKey.get(matchKey) ?? [];
      nodes.push(node.id);
      middlewareNodeIdsByKey.set(matchKey, nodes);
    });
  });

  const edges: DependencyGraphEdge[] = [];
  const edgeKeys = new Set<string>();
  const addEdge = (from: string, to: string, kind: DependencyGraphEdge["kind"]) => {
    if (from === to) return;
    const key = `${from}->${to}`;
    if (edgeKeys.has(key)) return;
    edgeKeys.add(key);
    edges.push({ from, to, kind });
  };

  preview.platformServices.forEach((item) => {
    const targetId = platformNodeIdsByKey.get(item.key);
    if (!targetId) return;
    item.requiredBy.forEach((requiredBy) => {
      (sourceNodeIdsByKey.get(requiredBy) ?? []).forEach((sourceId) => addEdge(sourceId, targetId, "platform"));
    });
  });
  preview.middleware.forEach((item) => {
    const targetIds = middlewareNodeIdsByKey.get(item.key) ?? [];
    if (!targetIds.length) return;
    item.requiredBy.forEach((requiredBy) => {
      (sourceNodeIdsByKey.get(requiredBy) ?? []).forEach((sourceId) => {
        targetIds.forEach((targetId) => addEdge(sourceId, targetId, "middleware"));
      });
    });
  });

  return { businessNodes, platformNodes, middlewareNodes, edges };
}

function runtimeGraphNodes(
  preview: PackagePreview,
  group: "business" | "platform" | "middleware",
  kind: DependencyGraphNodeKind,
  fallbackItems: PreviewDependencyItem[],
): DependencyGraphNode[] {
  const runtimeEntries = (preview.imageEntries ?? []).filter((item) => item.group === group);
  const nodes = runtimeEntries.map((item) => runtimeGraphNode(preview, item, kind)).filter((item): item is DependencyGraphNode => Boolean(item));
  const nodeKeys = new Set(nodes.flatMap((node) => node.matchKeys));
  fallbackItems.forEach((item) => {
    if (nodeKeys.has(item.key)) return;
    nodes.push(toGraphNode(item.key === preview.database.key ? "database" : kind, item));
  });
  if (group !== "middleware") return nodes;
  if (!nodes.some((node) => node.key === preview.database.key)) {
    nodes.push({
      id: `database:${preview.database.key}`,
      key: preview.database.key,
      label: preview.database.name,
      kind: "database",
      detail: preview.database.image,
      matchKeys: [preview.database.key],
    });
  }
  return nodes;
}

function toGraphNode(kind: DependencyGraphNodeKind, item: PreviewDependencyItem): DependencyGraphNode {
  return {
    id: `${kind}:${item.key}`,
    key: item.key,
    label: item.name,
    kind,
    detail: item.namespace || item.reason || item.key,
    matchKeys: [item.key],
  };
}

function runtimeGraphNode(preview: PackagePreview, item: PackagePreview["imageEntries"][number], kind: DependencyGraphNodeKind): DependencyGraphNode | null {
  const sourceRef = item.sourceRef || item.catalogRef || item.targetRef;
  const label = item.sourceContainer || item.sourcePod || imageName(sourceRef);
  if (!sourceRef || !label) return null;
  const key = `${item.group}:${item.sourceNamespace || "runtime"}:${item.sourcePod || imageName(sourceRef)}:${item.sourceContainer || imageName(sourceRef)}`;
  const matchKeys = runtimeMatchKeys(preview, item, kind);
  return {
    id: key,
    key,
    label,
    kind: kind === "middleware" && matchesRuntimeDependency(preview.database.key, preview.database.name, item) ? "database" : kind,
    detail: runtimeNodeDetail(item, sourceRef),
    matchKeys,
  };
}

function runtimeMatchKeys(preview: PackagePreview, item: PackagePreview["imageEntries"][number], kind: DependencyGraphNodeKind): string[] {
  if (kind === "business") {
    const matches = dependencyMatches(preview.businessServices, item);
    return matches.length ? matches : preview.businessServices.map((entry) => entry.key);
  }
  if (kind === "platform") {
    const matches = dependencyMatches(preview.platformServices, item);
    return matches;
  }
  const middlewareMatches = dependencyMatches(preview.middleware, item);
  if (middlewareMatches.length) return middlewareMatches;
  if (matchesRuntimeDependency(preview.database.key, preview.database.name, item)) return [preview.database.key];
  return [];
}

function dependencyMatches(items: PreviewDependencyItem[], image: PackagePreview["imageEntries"][number]) {
  return items
    .filter((item) => matchesRuntimeDependency(item.key, item.name, image))
    .map((item) => item.key);
}

function matchesRuntimeDependency(key: string, name: string, image: PackagePreview["imageEntries"][number]) {
  const haystack = normalizeGraphText([
    image.catalogRef,
    image.sourceRef,
    image.targetRef,
    image.sourceNamespace,
    image.sourcePod,
    image.sourceContainer,
  ].filter(Boolean).join(" "));
  const normalizedKey = normalizeGraphText(key);
  const normalizedName = normalizeGraphText(name);
  if (normalizedKey && haystack.includes(normalizedKey)) return true;
  if (normalizedName && haystack.includes(normalizedName)) return true;
  return key.split("-").some((part) => part.length >= 4 && haystack.includes(normalizeGraphText(part)));
}

function runtimeNodeDetail(item: PackagePreview["imageEntries"][number], sourceRef: string) {
  const namespace = item.sourceNamespace ? `${item.sourceNamespace}/` : "";
  const container = item.sourceContainer ? `${item.sourceContainer} · ` : "";
  return `${namespace}${container}${sourceRef}`;
}

function imageName(image: string) {
  const withoutDigest = image.split("@", 1)[0];
  const lastSegment = withoutDigest.split("/").pop() || withoutDigest;
  return lastSegment.split(":", 1)[0] || image;
}

function normalizeGraphText(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "");
}

function graphNodeClassName(kind: DependencyGraphNodeKind) {
  if (kind === "business") return styles.graphNodeBusiness;
  if (kind === "platform") return styles.graphNodePlatform;
  if (kind === "database") return styles.graphNodeDatabase;
  return styles.graphNodeMiddleware;
}

function graphNodeIcon(kind: DependencyGraphNodeKind) {
  if (kind === "business") return "ri-building-4-line";
  if (kind === "platform") return "ri-apps-2-line";
  if (kind === "database") return "ri-database-2-line";
  return "ri-server-line";
}

function taskStatusColor(status: PackageTask["status"]) {
  if (status === "completed") return "success";
  if (status === "failed") return "error";
  if (status === "canceled") return "default";
  if (status === "running") return "processing";
  return "default";
}

function auditStatusColor(status: string) {
  if (status === "completed" || status === "accepted") return "success";
  if (status === "failed" || status === "error") return "error";
  if (status === "dry-run") return "blue";
  return "default";
}

function exportDrawerTitle(key: ExportDrawerKey | null) {
  if (key === "preview") return "预览详情";
  if (key === "task") return "任务详情";
  if (key === "tasks") return "最近任务";
  if (key === "cleanup") return "产物清理";
  if (key === "audit") return "最近审计";
  return "";
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KiB`;
  if (value < 1024 * 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MiB`;
  return `${(value / 1024 / 1024 / 1024).toFixed(1)} GiB`;
}

function triggerBrowserDownload(url: string, filename: string) {
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
}

function mergeTaskIntoList(tasks: PackageTask[], task: PackageTask) {
  if (tasks.some((item) => item.taskId === task.taskId)) {
    return tasks.map((item) => (item.taskId === task.taskId ? task : item));
  }
  return [task, ...tasks].slice(0, 20);
}

function businessOptionsForEnv(items: DeploymentServiceOption[], sourceEnv: SourceEnv) {
  return items.filter((item) => item.registered && item.sourceEnv === sourceEnv && item.status !== "disabled");
}

function businessOptionValue(item: Pick<DeploymentServiceOption, "key" | "profile">) {
  return `${item.key}::${item.profile || ""}`;
}

function businessPlatformRowKey(item: Pick<DeploymentServiceOption, "sourceEnv" | "key" | "profile">) {
  return `${item.sourceEnv}:${item.key}:${item.profile || ""}`;
}

function parseBusinessOptionValue(value: string) {
  const [key, profile = ""] = value.split("::", 2);
  return { key, profile };
}

function serviceOptionsForEnv<T extends { sourceEnv?: SourceEnv | "" }>(items: T[], sourceEnv: SourceEnv) {
  return items.filter((item) => item.sourceEnv === sourceEnv);
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
