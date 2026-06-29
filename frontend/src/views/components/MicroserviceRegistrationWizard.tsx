import React from "react";
import { Button, Checkbox, Form, Input, InputNumber, Modal, Select, Steps } from "antd";
import type { FormInstance } from "antd";
import type { DeploymentPackageOptions, DeploymentServiceOption, SourceEnv } from "../../api/deploymentPackages";
import type { MicroserviceScaffoldOptions } from "../../api/microservices";
import type { SystemSettings } from "../../api/settings";
import type { MicroserviceWizardValues } from "../hooks/useMicroserviceRegistration";
import { businessPlatformValue, IMAGE_PATH_PATTERN, K8S_NAME_PATTERN, REGISTRY_HOST_PATTERN } from "./microserviceUtils";
import styles from "../MicroserviceRegistrationView.module.css";

const STEP_FIELDS: Array<Array<keyof MicroserviceWizardValues>> = [["sourceEnv", "businessPlatform"], ["serviceKey", "serviceName", "projectKind", "techStack", "description"], ["port", "middleware", "gitGroup", "imageRegistry", "imageNamespace", "k8sNamespace"], []];

interface Props {
  businessPlatforms: DeploymentServiceOption[];
  currentStep: number;
  deploymentOptions: DeploymentPackageOptions | null;
  form: FormInstance<MicroserviceWizardValues>;
  formValues: MicroserviceWizardValues;
  open: boolean;
  options: MicroserviceScaffoldOptions | null;
  selectedPlatform?: DeploymentServiceOption;
  submitting: boolean;
  systemSettings: SystemSettings | null;
  onClose: () => void;
  onNext: () => Promise<void>;
  onPrevious: () => void;
  onSubmit: () => void;
  onValuesChange: (_: unknown, values: MicroserviceWizardValues) => void;
}

export function MicroserviceRegistrationWizard(props: Props) {
  return (
    <Modal title="注册微服务" open={props.open} onCancel={props.onClose} width={760} destroyOnClose footer={footer(props)}>
      <Steps className={styles.steps} current={props.currentStep} items={[{ title: "业务平台" }, { title: "项目框架" }, { title: "构建部署" }, { title: "确认生成" }]} />
      <Form form={props.form} layout="vertical" onValuesChange={props.onValuesChange}>
        {props.currentStep === 0 ? <PlatformStep {...props} /> : null}
        {props.currentStep === 1 ? <ProjectStep {...props} /> : null}
        {props.currentStep === 2 ? <DeployStep {...props} /> : null}
        {props.currentStep === 3 ? <SummaryStep {...props} /> : null}
      </Form>
    </Modal>
  );
}

function footer(props: Props) {
  return [<Button key="cancel" onClick={props.onClose} disabled={props.submitting}>取消</Button>, <Button key="previous" onClick={props.onPrevious} disabled={props.currentStep === 0 || props.submitting}>上一步</Button>, props.currentStep < STEP_FIELDS.length - 1 ? <Button key="next" type="primary" onClick={() => void props.onNext()}>下一步</Button> : <Button key="submit" type="primary" loading={props.submitting} onClick={props.onSubmit}>注册并生成</Button>];
}

export function stepFields(step: number) {
  return STEP_FIELDS[step];
}

function PlatformStep({ businessPlatforms, deploymentOptions, form, onValuesChange }: Props) {
  return (
    <div className={styles.stepBody}>
      <Form.Item label="来源环境" name="sourceEnv" rules={[{ required: true, message: "请选择来源环境" }]}>
        <Select options={(deploymentOptions?.sourceEnvs ?? ["test"]).map((item) => ({ value: item, label: item === "dev" ? "开发环境" : "测试环境" }))} onChange={(value: SourceEnv) => { const first = (deploymentOptions?.businessServices ?? []).find((item) => item.registered && item.status !== "disabled" && item.sourceEnv === value); form.setFieldValue("businessPlatform", first ? businessPlatformValue(first) : ""); onValuesChange(null, form.getFieldsValue(true)); }} />
      </Form.Item>
      <Form.Item label="业务平台" name="businessPlatform" rules={[{ required: true, message: "请选择业务平台" }]}>
        <Select placeholder="请先注册业务平台" options={businessPlatforms.map((item) => ({ value: businessPlatformValue(item), label: `${item.name} / ${item.namespace || item.profile || item.key}` }))} />
      </Form.Item>
    </div>
  );
}

function ProjectStep({ options }: Props) {
  return (
    <div className={styles.stepGrid}>
      <Form.Item label="服务 Key" name="serviceKey" rules={[{ required: true }, { pattern: K8S_NAME_PATTERN, message: "仅支持小写字母、数字、中划线" }]}><Input placeholder="460mes-service" /></Form.Item>
      <Form.Item label="服务名称" name="serviceName" rules={[{ required: true }]}><Input placeholder="资产服务" /></Form.Item>
      <Form.Item label="项目类型" name="projectKind" rules={[{ required: true }]}><Select options={(options?.projectKinds ?? []).map((item) => ({ value: item.key, label: item.name }))} /></Form.Item>
      <Form.Item label="技术栈" name="techStack" rules={[{ required: true }]}><Select options={(options?.techStacks ?? []).map((item) => ({ value: item.key, label: item.name }))} /></Form.Item>
      <Form.Item className={styles.fullWidth} label="描述" name="description"><Input.TextArea rows={3} /></Form.Item>
    </div>
  );
}

function DeployStep({ options, systemSettings }: Props) {
  return (
    <div className={styles.stepGrid}>
      <div className={styles.fullWidth}><span className={styles.settingsHint}><i className="ri-settings-3-line" />默认读取系统设置：{systemSettings?.jenkins.baseUrl || "未配置 Jenkins"}</span></div>
      <Form.Item label="端口" name="port" rules={[{ required: true }]}><InputNumber min={1} max={65535} className={styles.fullControl} /></Form.Item>
      <Form.Item label="Git 分组" name="gitGroup" rules={[{ required: true }, { pattern: IMAGE_PATH_PATTERN, message: "仅支持小写路径片段" }]}><Input /></Form.Item>
      <Form.Item label="镜像仓库" name="imageRegistry" rules={[{ required: true }, { pattern: REGISTRY_HOST_PATTERN, message: "请输入仓库 Host" }]}><Input /></Form.Item>
      <Form.Item label="镜像命名空间" name="imageNamespace" rules={[{ required: true }, { pattern: IMAGE_PATH_PATTERN, message: "仅支持小写镜像路径片段" }]}><Input /></Form.Item>
      <Form.Item label="K8s namespace" name="k8sNamespace" rules={[{ pattern: K8S_NAME_PATTERN, message: "仅支持小写字母、数字、中划线" }]}><Input placeholder="留空使用业务平台 namespace" /></Form.Item>
      <Form.Item className={styles.fullWidth} label="中间件" name="middleware"><Checkbox.Group options={(options?.middleware ?? []).map((item) => ({ value: item.key, label: item.name }))} /></Form.Item>
    </div>
  );
}

function SummaryStep({ formValues, selectedPlatform }: Props) {
  return (
    <div className={styles.summary}>
      <SummaryItem label="来源环境" value={formValues.sourceEnv} />
      <SummaryItem label="业务平台" value={selectedPlatform ? `${selectedPlatform.name} / ${selectedPlatform.namespace}` : formValues.businessPlatform} />
      <SummaryItem label="服务" value={`${formValues.serviceName} (${formValues.serviceKey})`} />
      <SummaryItem label="镜像" value={`${formValues.imageRegistry}/${formValues.imageNamespace}/${formValues.serviceKey}`} />
      <SummaryItem label="中间件" value={(formValues.middleware || []).join(", ") || "无"} />
      <SummaryItem label="K8s namespace" value={formValues.k8sNamespace || selectedPlatform?.namespace || "使用业务平台 namespace"} />
    </div>
  );
}

function SummaryItem({ label, value }: { label: string; value: string }) {
  return <div className={styles.summaryItem}><span className={styles.muted}>{label}</span><span className={styles.mono}>{value}</span></div>;
}
