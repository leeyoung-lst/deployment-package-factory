import React, { useEffect, useMemo, useState } from "react";
import { App, Button, Checkbox, Empty, Form, Input, InputNumber, Select, Space, Spin, Tag } from "antd";
import {
  downloadMicroserviceScaffold,
  getMicroserviceScaffoldOptions,
  registerMicroservice,
  type MicroserviceScaffoldOptions,
  type MicroserviceScaffoldResult,
} from "../api/microservices";
import { getDeploymentPackageOptions, type DeploymentPackageOptions, type DeploymentServiceOption, type SourceEnv } from "../api/deploymentPackages";
import styles from "./MicroserviceRegistrationView.module.css";

const DEFAULT_VALUES = {
  serviceKey: "asset-service",
  serviceName: "资产服务",
  description: "",
  projectKind: "backend",
  techStack: "python-fastapi",
  port: 8000,
  middleware: ["redis", "postgresql"],
  sourceEnv: "test" as SourceEnv,
  businessPlatform: "",
  gitGroup: "business-services",
  imageRegistry: "registry.local",
  imageNamespace: "business",
  k8sNamespace: "",
};

export const MicroserviceRegistrationView: React.FC = () => {
  const { message } = App.useApp();
  const [form] = Form.useForm();
  const [options, setOptions] = useState<MicroserviceScaffoldOptions | null>(null);
  const [deploymentOptions, setDeploymentOptions] = useState<DeploymentPackageOptions | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<MicroserviceScaffoldResult | null>(null);
  const sourceEnv = Form.useWatch("sourceEnv", form) as SourceEnv | undefined;
  const businessPlatforms = useMemo(
    () => (deploymentOptions?.businessServices ?? []).filter((item) => item.registered && item.status !== "disabled" && item.sourceEnv === (sourceEnv || DEFAULT_VALUES.sourceEnv)),
    [deploymentOptions?.businessServices, sourceEnv],
  );

  useEffect(() => {
    void loadOptions();
  }, []);

  const loadOptions = async () => {
    setLoading(true);
    try {
      const [scaffoldOptions, packageOptions] = await Promise.all([
        getMicroserviceScaffoldOptions(),
        getDeploymentPackageOptions(),
      ]);
      setOptions(scaffoldOptions);
      setDeploymentOptions(packageOptions);
      const firstPlatform = packageOptions.businessServices.find((item) => item.registered && item.status !== "disabled");
      form.setFieldsValue({
        ...DEFAULT_VALUES,
        sourceEnv: firstPlatform?.sourceEnv || packageOptions.sourceEnvs[0] || DEFAULT_VALUES.sourceEnv,
        businessPlatform: firstPlatform ? businessPlatformValue(firstPlatform) : "",
      });
    } catch (error) {
      message.error(error instanceof Error ? error.message : "微服务注册选项加载失败");
    } finally {
      setLoading(false);
    }
  };

  const submit = async () => {
    try {
      const values = await form.validateFields();
      const platform = parseBusinessPlatformValue(values.businessPlatform);
      setSubmitting(true);
      const payload = await registerMicroservice({
        serviceKey: values.serviceKey,
        serviceName: values.serviceName,
        description: values.description || "",
        projectKind: values.projectKind,
        techStack: values.techStack,
        port: values.port,
        middleware: values.middleware || [],
        sourceEnv: values.sourceEnv,
        businessPlatformKey: platform.key,
        businessPlatformProfile: platform.profile,
        gitGroup: values.gitGroup,
        imageRegistry: values.imageRegistry,
        imageNamespace: values.imageNamespace,
        k8sNamespace: values.k8sNamespace || "",
      });
      setResult(payload);
      message.success("微服务项目已生成");
    } catch (error) {
      if (error instanceof Error) message.error(error.message);
    } finally {
      setSubmitting(false);
    }
  };

  const copyCommand = async (value: string) => {
    await navigator.clipboard.writeText(value);
    message.success("已复制");
  };

  return (
    <div className={styles.page}>
      <Spin spinning={loading}>
        <div className={styles.panel}>
          <Form form={form} layout="vertical" initialValues={DEFAULT_VALUES}>
            <h3 className={styles.sectionTitle}>业务归属</h3>
            <div className={styles.split}>
              <Form.Item label="来源环境" name="sourceEnv" rules={[{ required: true, message: "请选择来源环境" }]}>
                <Select
                  options={(deploymentOptions?.sourceEnvs ?? ["test"]).map((item) => ({ value: item, label: item === "dev" ? "开发环境" : "测试环境" }))}
                  onChange={() => form.setFieldValue("businessPlatform", "")}
                />
              </Form.Item>
              <Form.Item label="业务平台" name="businessPlatform" rules={[{ required: true, message: "请选择业务平台" }]}>
                <Select
                  placeholder="请先注册业务平台"
                  options={businessPlatforms.map((item) => ({
                    value: businessPlatformValue(item),
                    label: `${item.name} / ${item.namespace || item.profile || item.key}`,
                  }))}
                />
              </Form.Item>
            </div>

            <h3 className={styles.sectionTitle}>项目框架</h3>
            <div className={styles.split}>
              <Form.Item label="服务 Key" name="serviceKey" rules={[{ required: true, message: "请输入服务 Key" }]}>
                <Input placeholder="asset-service" />
              </Form.Item>
              <Form.Item label="服务名称" name="serviceName" rules={[{ required: true, message: "请输入服务名称" }]}>
                <Input placeholder="资产服务" />
              </Form.Item>
              <Form.Item label="项目类型" name="projectKind" rules={[{ required: true }]}>
                <Select options={(options?.projectKinds ?? []).map((item) => ({ value: item.key, label: item.name }))} />
              </Form.Item>
              <Form.Item label="技术栈" name="techStack" rules={[{ required: true }]}>
                <Select options={(options?.techStacks ?? []).map((item) => ({ value: item.key, label: item.name }))} />
              </Form.Item>
              <Form.Item label="端口" name="port" rules={[{ required: true, message: "请输入端口" }]}>
                <InputNumber min={1} max={65535} style={{ width: "100%" }} />
              </Form.Item>
              <Form.Item label="中间件" name="middleware">
                <Checkbox.Group options={(options?.middleware ?? []).map((item) => ({ value: item.key, label: item.name }))} />
              </Form.Item>
            </div>
            <Form.Item label="描述" name="description">
              <Input.TextArea rows={3} placeholder="业务功能说明" />
            </Form.Item>

            <h3 className={styles.sectionTitle}>构建部署</h3>
            <div className={styles.split}>
              <Form.Item label="Git 分组" name="gitGroup" rules={[{ required: true }]}>
                <Input />
              </Form.Item>
              <Form.Item label="镜像仓库" name="imageRegistry" rules={[{ required: true }]}>
                <Input />
              </Form.Item>
              <Form.Item label="镜像命名空间" name="imageNamespace" rules={[{ required: true }]}>
                <Input />
              </Form.Item>
              <Form.Item label="K8s namespace" name="k8sNamespace">
                <Input placeholder="留空使用业务平台 namespace" />
              </Form.Item>
            </div>
            <Space>
              <Button icon={<i className="ri-refresh-line" />} onClick={() => void loadOptions()}>刷新选项</Button>
              <Button type="primary" icon={<i className="ri-git-repository-line" />} loading={submitting} onClick={() => void submit()}>
                注册并生成项目
              </Button>
            </Space>
          </Form>
        </div>
      </Spin>

      <div className={styles.panel}>
        <h3 className={styles.sectionTitle}>生成结果</h3>
        {result ? (
          <div className={styles.resultGrid}>
            <div className={styles.resultRow}>
              <span className={styles.muted}>业务平台</span>
              <Space size={6} wrap>
                <Tag color="purple">{result.businessPlatformName}</Tag>
                <span className={styles.mono}>{result.businessPlatformNamespace}</span>
              </Space>
            </div>
            <div className={styles.resultRow}>
              <span className={styles.muted}>项目包</span>
              <span className={styles.mono}>{result.artifactName}</span>
            </div>
            <div className={styles.resultRow}>
              <span className={styles.muted}>SHA256</span>
              <span className={styles.mono}>{result.sha256}</span>
            </div>
            <div className={styles.resultRow}>
              <span className={styles.muted}>本地初始化</span>
              <Space.Compact style={{ width: "100%" }}>
                <Input className={styles.mono} value={result.cloneCommand} readOnly />
                <Button onClick={() => void copyCommand(result.cloneCommand)}>复制</Button>
              </Space.Compact>
            </div>
            <Space>
              <Button icon={<i className="ri-download-line" />} href={downloadMicroserviceScaffold(result.projectId)}>
                下载项目包
              </Button>
              <Button icon={<i className="ri-file-copy-line" />} onClick={() => void copyCommand(result.downloadCommand)}>
                复制下载命令
              </Button>
            </Space>
            <div className={styles.fileList}>
              {result.generatedFiles.map((item) => (
                <span key={item} className={styles.mono}>{item}</span>
              ))}
            </div>
          </div>
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="注册后显示项目下载信息" />
        )}
      </div>
    </div>
  );
};

function businessPlatformValue(item: DeploymentServiceOption) {
  return `${item.key}::${item.profile || ""}`;
}

function parseBusinessPlatformValue(value: string) {
  const [key, profile = ""] = value.split("::", 2);
  return { key, profile };
}
