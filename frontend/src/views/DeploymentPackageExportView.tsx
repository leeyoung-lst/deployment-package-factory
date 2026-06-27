import React, { useCallback, useEffect, useMemo, useState } from "react";
import { App, Button, Checkbox, Divider, Empty, Form, Input, Progress, Radio, Select, Space, Spin, Tag } from "antd";
import type { CheckboxChangeEvent } from "antd/es/checkbox";
import {
  createDeploymentPackage,
  deploymentPackageDownloadUrl,
  getDeploymentPackageOptions,
  getDeploymentPackageTask,
  previewDeploymentPackage,
  type BusinessSelection,
  type DeployMode,
  type DeploymentPackageOptions,
  type PackagePreview,
  type PackagePreviewRequest,
  type PackageTask,
  type SourceEnv,
} from "../api/deploymentPackages";
import styles from "./DeploymentPackageExportView.module.css";

const DEFAULT_TARGET = {
  env: "prod",
  domain: "prod.example.com",
  registry: "",
  namespacePrefix: "prod",
  storageClass: "",
  exportImages: false,
};

export const DeploymentPackageExportView: React.FC = () => {
  const { message } = App.useApp();
  const [form] = Form.useForm();
  const [options, setOptions] = useState<DeploymentPackageOptions | null>(null);
  const [projectKey, setProjectKey] = useState("");
  const [productVersion, setProductVersion] = useState("");
  const [sourceEnv, setSourceEnv] = useState<SourceEnv>("test");
  const [deployModes, setDeployModes] = useState<DeployMode[]>(["k8s", "docker-compose"]);
  const [platformServices, setPlatformServices] = useState<string[]>([]);
  const [businessServices, setBusinessServices] = useState<string[]>(["eam"]);
  const [database, setDatabase] = useState("postgres");
  const [preview, setPreview] = useState<PackagePreview | null>(null);
  const [task, setTask] = useState<PackageTask | null>(null);
  const [loadingOptions, setLoadingOptions] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [building, setBuilding] = useState(false);

  const requiredPlatformKeys = useMemo(
    () => options?.platformServices.filter((item) => item.required).map((item) => item.key) ?? [],
    [options],
  );

  const makePreviewPayload = useCallback((): PackagePreviewRequest => {
    const selectedBusiness: BusinessSelection[] = businessServices.map((name) => {
      const item = options?.businessServices.find((candidate) => candidate.key === name);
      return { name, profile: item?.profile || "" };
    });
    return {
      projectKey,
      productVersion,
      sourceEnv,
      deployModes,
      platformServices,
      businessServices: selectedBusiness,
      database,
    };
  }, [businessServices, database, deployModes, options?.businessServices, platformServices, productVersion, projectKey, sourceEnv]);

  const applyProjectDefaults = useCallback((key: string, sourceOptions = options) => {
    const project = sourceOptions?.projects.find((item) => item.key === key);
    setProjectKey(key);
    if (!project) return;
    setProductVersion(project.defaultVersion || project.versions[0] || "");
    setSourceEnv(project.defaultSourceEnv);
    setDeployModes(project.defaultDeployModes);
    setPlatformServices(project.defaultPlatformServices);
    setBusinessServices(project.defaultBusinessServices.map((item) => item.name));
    setDatabase(project.defaultDatabase);
    form.setFieldsValue({
      domain: project.domain,
      registry: project.registry,
      namespacePrefix: project.namespacePrefix,
      storageClass: project.storageClass,
    });
  }, [form, options]);

  const loadOptions = useCallback(async () => {
    setLoadingOptions(true);
    try {
      const payload = await getDeploymentPackageOptions();
      setOptions(payload);
      const required = payload.platformServices.filter((item) => item.required).map((item) => item.key);
      setPlatformServices((current) => Array.from(new Set([...required, ...current])));
      if (!payload.businessServices.some((item) => item.key === "eam")) {
        setBusinessServices(payload.businessServices.slice(0, 1).map((item) => item.key));
      }
      if (payload.databaseOptions.some((item) => item.key === "postgres")) {
        setDatabase("postgres");
      } else if (payload.databaseOptions[0]) {
        setDatabase(payload.databaseOptions[0].key);
      }
      if (payload.projects[0]) {
        applyProjectDefaults(payload.projects[0].key, payload);
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : "部署包选项加载失败");
    } finally {
      setLoadingOptions(false);
    }
  }, [applyProjectDefaults, message]);

  const refreshPreview = useCallback(async () => {
    if (!options) return;
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

  useEffect(() => {
    queueMicrotask(() => void loadOptions());
  }, [loadOptions]);

  useEffect(() => {
    if (!options) return;
    const timer = window.setTimeout(() => void refreshPreview(), 240);
    return () => window.clearTimeout(timer);
  }, [businessServices, database, deployModes, options, platformServices, productVersion, projectKey, refreshPreview, sourceEnv]);

  const onPlatformChange = (checkedValues: Array<string | number | boolean>) => {
    const selected = checkedValues.map(String);
    setPlatformServices(Array.from(new Set([...requiredPlatformKeys, ...selected])));
  };

  const onBusinessChange = (checkedValues: Array<string | number | boolean>) => {
    setBusinessServices(checkedValues.map(String));
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
          registry: values.registry || "",
          namespacePrefix: values.namespacePrefix,
          storageClass: values.storageClass || "",
          exportImages: values.imageMode === "image-archive",
        },
      });
      setTask(payload);
      message.success("部署任务已创建");
    } catch (error) {
      if (error instanceof Error) message.error(error.message);
    } finally {
      setBuilding(false);
    }
  };

  useEffect(() => {
    if (!task || task.status === "completed" || task.status === "failed") return;
    const timer = window.setInterval(() => {
      void getDeploymentPackageTask(task.taskId)
        .then((payload) => {
          setTask(payload);
          if (payload.status === "completed") message.success("部署包生成完成");
          if (payload.status === "failed") message.error(payload.error || "部署包生成失败");
        })
        .catch((error) => message.error(error instanceof Error ? error.message : "任务状态刷新失败"));
    }, 1200);
    return () => window.clearInterval(timer);
  }, [message, task]);

  return (
    <section className={`panel ${styles.page}`}>
      <div className="panel-header">
        <div>
          <h2>部署包导出</h2>
          <p>按环境、基础能力、业务产品和中间件依赖生成生产部署包</p>
        </div>
        <Space>
          <Button icon={<i className="ri-refresh-line" />} loading={loadingOptions} onClick={() => void loadOptions()}>刷新选项</Button>
          <Button type="primary" icon={<i className="ri-package-line" />} loading={building} onClick={() => void buildPackage()}>生成部署包</Button>
        </Space>
      </div>

      <div className={`panel-body ${styles.content}`}>
        <Spin spinning={loadingOptions}>
          <div className={styles.formPanel}>
            <Form form={form} layout="vertical" initialValues={{ ...DEFAULT_TARGET, imageMode: "image-manifest" }}>
              <h3 className={styles.sectionTitle}>导出范围</h3>
              <div className={styles.split}>
                <Form.Item label="项目">
                  <Select
                    value={projectKey}
                    options={(options?.projects ?? []).map((item) => ({ value: item.key, label: item.name }))}
                    onChange={(value) => applyProjectDefaults(value)}
                    placeholder="选择项目模板"
                  />
                </Form.Item>
                <Form.Item label="产品版本">
                  <Select
                    value={productVersion}
                    options={(options?.projects.find((item) => item.key === projectKey)?.versions ?? []).map((item) => ({ value: item, label: item }))}
                    onChange={(value) => setProductVersion(value)}
                    placeholder="选择版本"
                  />
                </Form.Item>
              </div>
              <div className={styles.split}>
                <Form.Item label="来源环境">
                  <Radio.Group value={sourceEnv} onChange={(event) => setSourceEnv(event.target.value)}>
                    {(options?.sourceEnvs ?? ["dev", "test"]).map((env) => (
                      <Radio.Button key={env} value={env}>{env === "dev" ? "开发环境" : "测试环境"}</Radio.Button>
                    ))}
                  </Radio.Group>
                </Form.Item>
                <Form.Item label="部署方式">
                  <Checkbox.Group value={deployModes} onChange={(value) => setDeployModes(value.map(String) as DeployMode[])}>
                    <Space direction="vertical">
                      {(options?.deployModes ?? ["k8s", "docker-compose"]).map((mode) => (
                        <Checkbox key={mode} value={mode}>{mode === "k8s" ? "Kubernetes" : "Docker Compose"}</Checkbox>
                      ))}
                    </Space>
                  </Checkbox.Group>
                </Form.Item>
              </div>

              <Divider />
              <h3 className={styles.sectionTitle}>基础平台服务</h3>
              <Checkbox.Group className={styles.serviceGrid} value={platformServices} onChange={onPlatformChange}>
                {(options?.platformServices ?? []).map((item) => (
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

              <Divider />
              <h3 className={styles.sectionTitle}>业务平台服务</h3>
              <Checkbox.Group className={styles.serviceGrid} value={businessServices} onChange={onBusinessChange}>
                {(options?.businessServices ?? []).map((item) => (
                  <Checkbox key={item.key} value={item.key}>
                    <span className={styles.serviceItem}>
                      <span className={styles.serviceMain}>
                        <i className="ri-apps-2-line" />
                        <span className={styles.serviceName}>{item.name}</span>
                      </span>
                      <span className={styles.muted}>{item.profile || item.namespaceGroup}</span>
                    </span>
                  </Checkbox>
                ))}
              </Checkbox.Group>

              <Divider />
              <div className={styles.split}>
                <Form.Item label="数据库">
                  <Radio.Group value={database} onChange={(event) => setDatabase(event.target.value)}>
                    <Space direction="vertical">
                      {(options?.databaseOptions ?? []).map((item) => (
                        <Radio key={item.key} value={item.key}>
                          {item.name}
                          <Tag color={item.domestic ? "red" : "blue"} style={{ marginLeft: 8 }}>{item.domestic ? "国产化" : "非国产化"}</Tag>
                        </Radio>
                      ))}
                    </Space>
                  </Radio.Group>
                </Form.Item>
                <Form.Item label="镜像模式" name="imageMode">
                  <Select
                    options={[
                      { value: "image-manifest", label: "镜像清单：生成 pull/save/load 脚本" },
                      { value: "image-archive", label: "镜像归档：执行 docker pull/save 并打包 tar" },
                    ]}
                  />
                </Form.Item>
              </div>

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
                <Form.Item label="镜像仓库" name="registry">
                  <Input placeholder="registry.example.com/project" />
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
            {preview ? <PreviewSummary preview={preview} /> : <Empty description="请选择导出范围后预览" />}
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
                  <div className={styles.resultRow}>
                    <span className={styles.muted}>产物路径</span>
                    <span className={styles.mono}>{task.result.artifactPath}</span>
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
                  type="primary"
                  icon={<i className="ri-download-line" />}
                  href={task.result ? deploymentPackageDownloadUrl(task.result.packageId) : undefined}
                  disabled={!task.result}
                >
                  下载部署包
                </Button>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
};

function PreviewSummary({ preview }: { preview: PackagePreview }) {
  return (
    <div className={styles.page}>
      <div className={styles.previewGrid}>
        <DependencyBlock title="基础平台" items={preview.platformServices} color="blue" />
        <DependencyBlock title="业务平台" items={preview.businessServices} color="purple" />
        <DependencyBlock title="中间件" items={preview.middleware} color="cyan" />
        <div className={styles.previewBlock}>
          <h3>数据库</h3>
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
          {Object.entries(preview.images).map(([group, images]) => (
            <div className={styles.imageGroup} key={group}>
              <strong>{group}</strong>
              <div className={styles.tagList}>
                {images.map((image) => <Tag key={`${group}-${image}`}>{image}</Tag>)}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function taskStatusColor(status: PackageTask["status"]) {
  if (status === "completed") return "success";
  if (status === "failed") return "error";
  if (status === "running") return "processing";
  return "default";
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
