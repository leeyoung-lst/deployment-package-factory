import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { App, Button, Checkbox, Divider, Empty, Form, Input, Modal, Popconfirm, Progress, Radio, Select, Space, Spin, Tabs, Tag } from "antd";
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
  const [disablingBusinessKey, setDisablingBusinessKey] = useState("");
  const [targetDraft, setTargetDraft] = useState<TargetDraft>({ ...DEFAULT_TARGET, imageMode: DEFAULT_IMAGE_MODE });

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

  const makePreviewPayload = useCallback((): PackagePreviewRequest => {
    const selectedBusiness: BusinessSelection[] = businessServices.map((name) => {
      const item = options?.businessServices.find((candidate) => candidate.key === name);
      return { name, profile: item?.profile || "" };
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
    setBusinessServices(project.defaultBusinessServices.map((item) => item.name).filter((key) => businessOptionsForEnv(sourceOptions?.businessServices ?? [], project.defaultSourceEnv).some((item) => item.key === key)));
    const projectDatabases = serviceOptionsForEnv(sourceOptions?.databaseOptions ?? [], project.defaultSourceEnv);
    setDatabase(projectDatabases.some((item) => item.key === project.defaultDatabase) ? project.defaultDatabase : (projectDatabases[0]?.key ?? ""));
    form.setFieldsValue({
      domain: project.domain,
      registry: project.registry,
      namespacePrefix: project.namespacePrefix,
      storageClass: project.storageClass,
    });
    setTargetDraft((current) => ({
      ...current,
      domain: project.domain,
      registry: project.registry,
      namespacePrefix: project.namespacePrefix,
      storageClass: project.storageClass,
    }));
  }, [form, options]);

  const applyProjectDefaultsFromOptions = useCallback((key: string, sourceOptions: DeploymentPackageOptions) => {
    const project = sourceOptions.projects.find((item) => item.key === key);
    setProjectKey(key);
    if (!project) return;
    setProductVersion(project.defaultVersion || project.versions[0] || "");
    setSourceEnv(project.defaultSourceEnv);
    setDeployMode(project.defaultDeployModes[0] || "k8s");
    setPlatformServices(project.defaultPlatformServices.filter((key) => serviceOptionsForEnv(sourceOptions.platformServices, project.defaultSourceEnv).some((item) => item.key === key)));
    setBusinessServices(project.defaultBusinessServices.map((item) => item.name).filter((key) => businessOptionsForEnv(sourceOptions.businessServices, project.defaultSourceEnv).some((item) => item.key === key)));
    const projectDatabases = serviceOptionsForEnv(sourceOptions.databaseOptions, project.defaultSourceEnv);
    setDatabase(projectDatabases.some((item) => item.key === project.defaultDatabase) ? project.defaultDatabase : (projectDatabases[0]?.key ?? ""));
    form.setFieldsValue({
      domain: project.domain,
      registry: project.registry,
      namespacePrefix: project.namespacePrefix,
      storageClass: project.storageClass,
    });
    setTargetDraft((current) => ({
      ...current,
      domain: project.domain,
      registry: project.registry,
      namespacePrefix: project.namespacePrefix,
      storageClass: project.storageClass,
    }));
  }, [form]);

  const loadOptions = useCallback(async () => {
    setLoadingOptions(true);
    try {
      const payload = await getDeploymentPackageOptions();
      setOptions(payload);
      const nextSourceEnv = payload.sourceEnvs.includes(sourceEnv) ? sourceEnv : (payload.sourceEnvs[0] ?? "test");
      setSourceEnv(nextSourceEnv);
      const runtimePlatform = serviceOptionsForEnv(payload.platformServices, nextSourceEnv);
      const required = runtimePlatform.filter((item) => item.required).map((item) => item.key);
      setPlatformServices((current) => Array.from(new Set([...required, ...current])));
      const runtimeBusiness = businessOptionsForEnv(payload.businessServices, nextSourceEnv);
      setBusinessServices((current) => current.filter((key) => runtimeBusiness.some((item) => item.key === key)));
      const runtimeDatabases = serviceOptionsForEnv(payload.databaseOptions, nextSourceEnv);
      if (runtimeDatabases.some((item) => item.key === "postgres")) {
        setDatabase("postgres");
      } else if (runtimeDatabases[0]) {
        setDatabase(runtimeDatabases[0].key);
      } else {
        setDatabase("");
      }
      if (payload.projects[0]) {
        applyProjectDefaultsFromOptions(payload.projects[0].key, payload);
      } else {
        setProjectKey("");
        setProductVersion("");
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : "部署包选项加载失败");
    } finally {
      setLoadingOptions(false);
    }
  }, [applyProjectDefaultsFromOptions, message]);

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
    setDisablingBusinessKey(`${item.sourceEnv}:${item.key}`);
    try {
      await disableBusinessPlatform(item.sourceEnv as SourceEnv, item.key);
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
      const blob = await downloadDeploymentPackage(task.result.packageId);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${task.result.packageId}.tar.gz`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
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
      const blob = await downloadDeploymentPackageChecksum(task.result.packageId);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${task.result.packageId}.tar.gz.sha256`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
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
          <Button type="primary" icon={<i className="ri-package-line" />} loading={building} onClick={() => void buildPackage()}>生成部署包</Button>
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
                    <div className={styles.formPanel}>
            <Form
              form={form}
              layout="vertical"
              initialValues={{ ...DEFAULT_TARGET, imageMode: DEFAULT_IMAGE_MODE }}
              onValuesChange={(_, values) => setTargetDraft((current) => ({ ...current, ...values }))}
            >
              <h3 className={styles.sectionTitle}>导出范围</h3>
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

              <Divider />
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

              <Divider />
              <h3 className={styles.sectionTitle}>业务平台服务</h3>
              <Checkbox.Group className={styles.serviceGrid} value={businessServices} onChange={onBusinessChange}>
                {businessOptionsForSourceEnv.map((item) => (
                  <Checkbox key={`${item.sourceEnv}-${item.key}`} value={item.key}>
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

              <Divider />
              <h3 className={styles.sectionTitle}>中间件服务</h3>
              <div className={styles.split}>
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
                <Form.Item label="镜像模式" name="imageMode">
                  <Select
                    options={[
                      { value: "image-archive", label: "镜像归档：导出离线镜像 tar" },
                      { value: "image-manifest", label: "镜像清单：仅生成 pull/save/load 脚本" },
                    ]}
                  />
                </Form.Item>
              </div>
              <ImageEnvironmentStatus value={imageEnvironment} loading={imageEnvironmentLoading} />

              <Divider />
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
            </Form>
                    </div>
                  </Spin>

                  <div className={styles.page}>
          <div className={styles.previewPanel}>
            <div className="panel-header" style={{ padding: 0, marginBottom: 12 }}>
              <div>
                <h2 style={{ fontSize: 18 }}>依赖预览</h2>
                <p>中间件会根据基础能力与业务服务自动匹配</p>
              </div>
              <Button icon={<i className="ri-eye-line" />} loading={previewing} onClick={() => void refreshPreview()}>预览</Button>
            </div>
            {preview ? <PreviewSummary preview={preview} project={selectedProject} targetProfile={targetDraft} /> : <Empty description="请选择导出范围后预览" />}
          </div>

          {task ? (
            <div className={styles.resultPanel}>
              <h3 className={styles.sectionTitle}>任务状态</h3>
              <div className={styles.resultRow}>
                <span className={styles.muted}>任务 ID</span>
                <span className={styles.mono}>{task.taskId}</span>
              </div>
              <div className={styles.resultRow}>
                <span className={styles.muted}>状态</span>
                <Space>
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
              <div className={styles.actions}>
                <Button
                  icon={<i className="ri-close-circle-line" />}
                  loading={taskActionLoading}
                  disabled={task.status !== "pending" && task.status !== "running"}
                  onClick={() => void cancelTask()}
                >
                  取消任务
                </Button>
                <Button
                  icon={<i className="ri-restart-line" />}
                  loading={taskActionLoading}
                  disabled={task.status !== "failed" && task.status !== "canceled"}
                  onClick={() => void retryTask()}
                >
                  重试任务
                </Button>
                <Button
                  icon={<i className="ri-file-shield-2-line" />}
                  loading={checksumDownloadLoading}
                  onClick={() => void downloadTaskChecksum()}
                  disabled={!task.result || !task.artifactAvailable}
                >
                  下载校验文件
                </Button>
                <Button
                  type="primary"
                  icon={<i className="ri-download-line" />}
                  loading={downloadLoading}
                  onClick={() => void downloadTaskArtifact()}
                  disabled={!task.result || !task.artifactAvailable}
                >
                  {task.result && !task.artifactAvailable ? "产物已清理" : "下载部署包"}
                </Button>
              </div>
            </div>
          ) : null}

          <TaskListPanel
            tasks={tasks}
            loading={tasksLoading}
            selectedTaskId={task?.taskId}
            onSelect={(item) => setTask(item)}
            onRefresh={() => void refreshTasks()}
          />

          <CleanupPanel
            result={cleanupResult}
            loading={cleanupLoading}
            onDryRun={() => void runCleanup(true)}
            onCleanup={() => void runCleanup(false)}
          />

          <AuditPanel
            events={auditEvents}
            loading={auditLoading}
            onRefresh={() => void refreshAuditEvents()}
          />
                  </div>
                </div>
              ),
            },
          ]}
        />
      </div>

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
                    loading={disablingBusinessKey === `${item.sourceEnv}:${item.key}`}
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

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KiB`;
  if (value < 1024 * 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MiB`;
  return `${(value / 1024 / 1024 / 1024).toFixed(1)} GiB`;
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
