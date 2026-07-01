import React from "react";
import { Button, Form, Modal, Steps } from "antd";
import type { FormInstance } from "antd";
import type { DeploymentPackageOptions, DeploymentServiceOption } from "../../api/deploymentPackages";
import type { MicroserviceScaffoldOptions } from "../../api/microservices";
import type { SystemSettings } from "../../api/settings";
import type { MicroserviceWizardValues } from "../hooks/useMicroserviceRegistration";
import { DependencyStep } from "./microserviceWizard/DependencyStep";
import { DeployStep } from "./microserviceWizard/DeployStep";
import { PlatformStep } from "./microserviceWizard/PlatformStep";
import { ProjectStep } from "./microserviceWizard/ProjectStep";
import { SummaryStep } from "./microserviceWizard/SummaryStep";
import { TechStackStep } from "./microserviceWizard/TechStackStep";
import styles from "../MicroserviceRegistrationView.module.css";

const STEP_FIELDS: Array<Array<keyof MicroserviceWizardValues>> = [["sourceEnv", "businessPlatform"], ["serviceKey", "serviceName", "description"], ["projectKind", "techStack", "microFrontendFramework"], ["port", "gitGroup", "imageRegistry", "imageNamespace"], ["middleware", "k8sNamespace"], []];
const REQUIRED_FIELDS: Array<Array<keyof MicroserviceWizardValues>> = [["sourceEnv", "businessPlatform"], ["serviceKey", "serviceName"], ["projectKind", "techStack"], ["port", "gitGroup", "imageRegistry", "imageNamespace"], [], []];
export const WIZARD_STEP_COUNT = STEP_FIELDS.length;

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
  const stepProps = {
    businessPlatforms: props.businessPlatforms,
    deploymentOptions: props.deploymentOptions,
    form: props.form,
    formValues: props.formValues,
    options: props.options,
    selectedPlatform: props.selectedPlatform,
    systemSettings: props.systemSettings,
    onValuesChange: props.onValuesChange,
  };

  return (
    <Modal title="注册微服务" open={props.open} onCancel={props.onClose} width={760} destroyOnClose footer={footer(props)}>
      <Steps className={styles.steps} current={props.currentStep} items={[{ title: "业务平台" }, { title: "服务信息" }, { title: "技术栈" }, { title: "构建部署" }, { title: "运行依赖" }, { title: "确认生成" }]} />
      <Form form={props.form} layout="vertical" onValuesChange={props.onValuesChange}>
        {props.currentStep === 0 ? <PlatformStep {...stepProps} /> : null}
        {props.currentStep === 1 ? <ProjectStep {...stepProps} /> : null}
        {props.currentStep === 2 ? <TechStackStep {...stepProps} /> : null}
        {props.currentStep === 3 ? <DeployStep {...stepProps} /> : null}
        {props.currentStep === 4 ? <DependencyStep {...stepProps} /> : null}
        {props.currentStep === 5 ? <SummaryStep {...stepProps} /> : null}
      </Form>
    </Modal>
  );
}

function footer(props: Props) {
  const invalid = isStepInvalid(props);
  return [<Button key="cancel" onClick={props.onClose} disabled={props.submitting}>取消</Button>, <Button key="previous" onClick={props.onPrevious} disabled={props.currentStep === 0 || props.submitting}>上一步</Button>, props.currentStep < STEP_FIELDS.length - 1 ? <Button key="next" type="primary" disabled={invalid || props.submitting} onClick={() => void props.onNext()}>下一步</Button> : <Button key="submit" type="primary" disabled={invalid} loading={props.submitting} onClick={props.onSubmit}>注册并生成</Button>];
}

function isStepInvalid(props: Props) {
  return REQUIRED_FIELDS[props.currentStep].some((field) => {
    const value = props.formValues[field];
    return value === undefined || value === null || value === "";
  });
}

export function stepFields(step: number) {
  return STEP_FIELDS[step];
}
