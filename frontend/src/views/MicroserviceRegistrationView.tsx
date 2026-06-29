import React, { useEffect, useMemo, useState } from "react";
import { App, Button, Checkbox, Empty, Form, Input, InputNumber, Modal, Select, Space, Spin, Steps, Tag } from "antd";
import {
  downloadMicroserviceScaffold,
  getMicroserviceScaffoldOptions,
  listMicroservices,
  registerMicroservice,
  type MicroserviceScaffoldOptions,
  type MicroserviceScaffoldResult,
  type RegisteredMicroservice,
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

type WizardValues = typeof DEFAULT_VALUES;

const STEP_FIELDS: Array<Array<keyof WizardValues>> = [
  ["sourceEnv", "businessPlatform"],
  ["serviceKey", "serviceName", "projectKind", "techStack", "description"],
  ["port", "middleware", "gitGroup", "imageRegistry", "imageNamespace", "k8sNamespace"],
  [],
];

export const MicroserviceRegistrationView: React.FC = () => {
  const { message } = App.useApp();
  const [form] = Form.useForm<WizardValues>();
  const [options, setOptions] = useState<MicroserviceScaffoldOptions | null>(null);
  const [deploymentOptions, setDeploymentOptions] = useState<DeploymentPackageOptions | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [formValues, setFormValues] = useState<WizardValues>(DEFAULT_VALUES);
  const [result, setResult] = useState<MicroserviceScaffoldResult | null>(null);
  const [registeredServices, setRegisteredServices] = useState<RegisteredMicroservice[]>([]);

  const sourceEnv = Form.useWatch("sourceEnv", form) as SourceEnv | undefined;
  const businessPlatforms = useMemo(
    () => (deploymentOptions?.businessServices ?? []).filter((item) => item.registered && item.status !== "disabled" && item.sourceEnv === (sourceEnv || DEFAULT_VALUES.sourceEnv)),
    [deploymentOptions?.businessServices, sourceEnv],
  );
  const selectedPlatform = useMemo(
    () => businessPlatforms.find((item) => businessPlatformValue(item) === formValues.businessPlatform),
    [businessPlatforms, formValues.businessPlatform],
  );

  useEffect(() => {
    void loadOptions();
  }, []);

  const loadOptions = async () => {
    setLoading(true);
    try {
      const [scaffoldOptions, packageOptions, services] = await Promise.all([
        getMicroserviceScaffoldOptions(),
        getDeploymentPackageOptions(),
        listMicroservices(),
      ]);
      setOptions(scaffoldOptions);
      setDeploymentOptions(packageOptions);
      setRegisteredServices(services);
      const firstPlatform = packageOptions.businessServices.find((item) => item.registered && item.status !== "disabled");
      const nextValues = {
        ...DEFAULT_VALUES,
        sourceEnv: firstPlatform?.sourceEnv || packageOptions.sourceEnvs[0] || DEFAULT_VALUES.sourceEnv,
        businessPlatform: firstPlatform ? businessPlatformValue(firstPlatform) : "",
      };
      form.setFieldsValue(nextValues);
      setFormValues(nextValues);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "微服务注册选项加载失败");
    } finally {
      setLoading(false);
    }
  };

  const openWizard = () => {
    setCurrentStep(0);
    form.setFieldsValue(formValues);
    setWizardOpen(true);
  };

  const closeWizard = () => {
    if (!submitting) setWizardOpen(false);
  };

  const goNext = async () => {
    await form.validateFields(STEP_FIELDS[currentStep]);
    setFormValues(form.getFieldsValue(true));
    setCurrentStep((value) => Math.min(value + 1, STEP_FIELDS.length - 1));
  };

  const goPrevious = () => {
    setFormValues(form.getFieldsValue(true));
    setCurrentStep((value) => Math.max(value - 1, 0));
  };

  const submit = async () => {
    try {
      await form.validateFields();
      const values = form.getFieldsValue(true);
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
      setFormValues(values);
      setRegisteredServices(await listMicroservices());
      setWizardOpen(false);
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

  const refreshServices = async () => {
    try {
      setRegisteredServices(await listMicroservices());
    } catch (error) {
      message.error(error instanceof Error ? error.message : "微服务列表刷新失败");
    }
  };

  return (
    <div className={styles.page}>
      <Spin spinning={loading}>
        <div className={styles.toolbar}>
          <div>
            <h3 className={styles.title}>微服务注册</h3>
            <div className={styles.muted}>通过向导生成项目骨架、部署脚本和流水线文件。</div>
          </div>
          <Space wrap>
            <Button icon={<i className="ri-refresh-line" />} onClick={() => void loadOptions()}>刷新</Button>
            <Button type="primary" icon={<i className="ri-add-circle-line" />} onClick={openWizard} disabled={!businessPlatforms.length}>
              注册微服务
            </Button>
          </Space>
        </div>

        <div className={styles.contentGrid}>
          <section className={styles.panel}>
            <div className={styles.panelTitleRow}>
              <h3 className={styles.sectionTitle}>生成结果</h3>
              {result ? <Tag color="green">已生成</Tag> : null}
            </div>
            {result ? (
              <div className={styles.resultGrid}>
                <ResultRow label="业务平台">
                  <Space size={6} wrap>
                    <Tag color="purple">{result.businessPlatformName}</Tag>
                    <span className={styles.mono}>{result.businessPlatformNamespace}</span>
                  </Space>
                </ResultRow>
                <ResultRow label="项目包"><span className={styles.mono}>{result.artifactName}</span></ResultRow>
                <ResultRow label="SHA256"><span className={styles.mono}>{result.sha256}</span></ResultRow>
                <ResultRow label="本地初始化">
                  <Space.Compact className={styles.commandBox}>
                    <Input className={styles.mono} value={result.cloneCommand} readOnly />
                    <Button onClick={() => void copyCommand(result.cloneCommand)}>复制</Button>
                  </Space.Compact>
                </ResultRow>
                <Space wrap>
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
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="点击注册微服务开始生成项目" />
            )}
          </section>

          <section className={styles.panel}>
            <div className={styles.panelTitleRow}>
              <h3 className={styles.sectionTitle}>已注册微服务</h3>
              <Button size="small" icon={<i className="ri-refresh-line" />} onClick={() => void refreshServices()}>刷新列表</Button>
            </div>
            {registeredServices.length ? (
              <div className={styles.serviceList}>
                {registeredServices.map((item) => (
                  <div key={`${item.sourceEnv}-${item.businessPlatformKey}-${item.businessPlatformProfile}-${item.serviceKey}`} className={styles.serviceItem}>
                    <span>
                      <strong>{item.serviceName}</strong>
                      <span className={styles.mono}>{item.serviceKey}</span>
                    </span>
                    <span>
                      <Tag color="purple">{item.businessPlatformName}</Tag>
                      <Tag color="blue">{item.sourceEnv}</Tag>
                    </span>
                    <span className={styles.mono}>{item.image}</span>
                  </div>
                ))}
              </div>
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无已注册微服务" />
            )}
          </section>
        </div>
      </Spin>

      <Modal
        title="注册微服务"
        open={wizardOpen}
        onCancel={closeWizard}
        width={760}
        destroyOnClose
        footer={[
          <Button key="cancel" onClick={closeWizard} disabled={submitting}>取消</Button>,
          <Button key="previous" onClick={goPrevious} disabled={currentStep === 0 || submitting}>上一步</Button>,
          currentStep < STEP_FIELDS.length - 1 ? (
            <Button key="next" type="primary" onClick={() => void goNext()}>下一步</Button>
          ) : (
            <Button key="submit" type="primary" loading={submitting} onClick={() => void submit()}>注册并生成</Button>
          ),
        ]}
      >
        <Steps
          className={styles.steps}
          current={currentStep}
          items={[
            { title: "业务平台" },
            { title: "项目框架" },
            { title: "构建部署" },
            { title: "确认生成" },
          ]}
        />
        <Form
          form={form}
          layout="vertical"
          initialValues={DEFAULT_VALUES}
          onValuesChange={(_, values) => setFormValues(values)}
        >
          {currentStep === 0 ? (
            <div className={styles.stepBody}>
              <Form.Item label="来源环境" name="sourceEnv" rules={[{ required: true, message: "请选择来源环境" }]}>
                <Select
                  options={(deploymentOptions?.sourceEnvs ?? ["test"]).map((item) => ({ value: item, label: item === "dev" ? "开发环境" : "测试环境" }))}
                  onChange={(value: SourceEnv) => {
                    const firstPlatform = (deploymentOptions?.businessServices ?? []).find((item) => item.registered && item.status !== "disabled" && item.sourceEnv === value);
                    form.setFieldValue("businessPlatform", firstPlatform ? businessPlatformValue(firstPlatform) : "");
                    setFormValues(form.getFieldsValue(true));
                  }}
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
          ) : null}

          {currentStep === 1 ? (
            <div className={styles.stepGrid}>
              <Form.Item
                label="服务 Key"
                name="serviceKey"
                rules={[
                  { required: true, message: "请输入服务 Key" },
                  {
                    pattern: /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/,
                    message: "仅支持小写字母、数字、中划线，首尾必须是字母或数字",
                  },
                ]}
              >
                <Input placeholder="460mes-service" />
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
              <Form.Item className={styles.fullWidth} label="描述" name="description">
                <Input.TextArea rows={3} placeholder="业务功能说明" />
              </Form.Item>
            </div>
          ) : null}

          {currentStep === 2 ? (
            <div className={styles.stepGrid}>
              <Form.Item label="端口" name="port" rules={[{ required: true, message: "请输入端口" }]}>
                <InputNumber min={1} max={65535} className={styles.fullControl} />
              </Form.Item>
              <Form.Item label="Git 分组" name="gitGroup" rules={[{ required: true, message: "请输入 Git 分组" }]}>
                <Input />
              </Form.Item>
              <Form.Item label="镜像仓库" name="imageRegistry" rules={[{ required: true, message: "请输入镜像仓库" }]}>
                <Input />
              </Form.Item>
              <Form.Item label="镜像命名空间" name="imageNamespace" rules={[{ required: true, message: "请输入镜像命名空间" }]}>
                <Input />
              </Form.Item>
              <Form.Item label="K8s namespace" name="k8sNamespace">
                <Input placeholder="留空使用业务平台 namespace" />
              </Form.Item>
              <Form.Item className={styles.fullWidth} label="中间件" name="middleware">
                <Checkbox.Group options={(options?.middleware ?? []).map((item) => ({ value: item.key, label: item.name }))} />
              </Form.Item>
            </div>
          ) : null}

          {currentStep === 3 ? (
            <div className={styles.summary}>
              <SummaryItem label="来源环境" value={formValues.sourceEnv} />
              <SummaryItem label="业务平台" value={selectedPlatform ? `${selectedPlatform.name} / ${selectedPlatform.namespace}` : formValues.businessPlatform} />
              <SummaryItem label="服务" value={`${formValues.serviceName} (${formValues.serviceKey})`} />
              <SummaryItem label="技术栈" value={formValues.techStack} />
              <SummaryItem label="中间件" value={(formValues.middleware || []).join(", ") || "无"} />
              <SummaryItem label="镜像" value={`${formValues.imageRegistry}/${formValues.imageNamespace}/${formValues.serviceKey}`} />
              <SummaryItem label="端口" value={String(formValues.port)} />
              <SummaryItem label="K8s namespace" value={formValues.k8sNamespace || selectedPlatform?.namespace || "使用业务平台 namespace"} />
            </div>
          ) : null}
        </Form>
      </Modal>
    </div>
  );
};

function ResultRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className={styles.resultRow}>
      <span className={styles.muted}>{label}</span>
      <span>{children}</span>
    </div>
  );
}

function SummaryItem({ label, value }: { label: string; value: string }) {
  return (
    <div className={styles.summaryItem}>
      <span className={styles.muted}>{label}</span>
      <span className={styles.mono}>{value}</span>
    </div>
  );
}

function businessPlatformValue(item: DeploymentServiceOption) {
  return `${item.key}::${item.profile || ""}`;
}

function parseBusinessPlatformValue(value: string) {
  const [key, profile = ""] = value.split("::", 2);
  return { key, profile };
}
