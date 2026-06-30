import React from "react";
import { Button, Form, Modal, Space, Steps } from "antd";
import type { FormInstance } from "antd";
import { DEFAULT_IMAGE_MODE, DEFAULT_TARGET, EXPORT_WIZARD_STEPS, type TargetDraft } from "./deploymentPackageUtils";
import { DeploymentRuntimeConfigStep } from "./DeploymentRuntimeConfigStep";
import { ConfirmStep, MiddlewareImageStep, PlatformServicesStep, ProductRangeStep, TargetProfileStep, type WizardStepProps } from "./DeploymentPackageWizardSteps";
import styles from "../DeploymentPackageExportView.module.css";

interface Props extends WizardStepProps {
  building: boolean;
  buildDisabled: boolean;
  form: FormInstance;
  open: boolean;
  step: number;
  onBuild: () => void;
  onCancel: () => void;
  onNext: () => void;
  onPrevious: () => void;
  onTargetDraftChange: (updater: (current: TargetDraft) => TargetDraft) => void;
}

export function DeploymentPackageWizardModal(props: Props) {
  return (
    <Modal title="创建部署包" open={props.open} onCancel={props.onCancel} width="min(1040px, 94vw)" destroyOnClose={false} footer={<WizardFooter {...props} />}>
      <Form form={props.form} layout="vertical" initialValues={{ ...DEFAULT_TARGET, imageMode: DEFAULT_IMAGE_MODE }} onValuesChange={(_, values) => props.onTargetDraftChange((current) => ({ ...current, ...values }))}>
        <Steps className={styles.wizardSteps} size="small" current={props.step} items={EXPORT_WIZARD_STEPS.map((title) => ({ title }))} />
        <div className={styles.wizardBody}>
          {props.step === 0 ? <ProductRangeStep {...props} /> : null}
          {props.step === 1 ? <PlatformServicesStep {...props} /> : null}
          {props.step === 2 ? <MiddlewareImageStep {...props} /> : null}
          {props.step === 3 ? <DeploymentRuntimeConfigStep runtimeConfig={props.runtimeConfig} overrides={props.runtimeConfigOverrides} onChange={props.onRuntimeConfigChange} /> : null}
          {props.step === 4 ? <TargetProfileStep /> : null}
          {props.step === 5 ? <ConfirmStep {...props} /> : null}
        </div>
      </Form>
    </Modal>
  );
}

function WizardFooter(props: Props) {
  return (
    <div className={styles.wizardFooter}>
      <Button onClick={props.onCancel}>取消</Button>
      <Space>
        <Button disabled={props.step === 0} onClick={props.onPrevious}>上一步</Button>
        {props.step < EXPORT_WIZARD_STEPS.length - 1 ? (
          <Button type="primary" onClick={props.onNext}>下一步</Button>
        ) : (
          <Button type="primary" icon={<i className="ri-package-line" />} loading={props.building} disabled={props.buildDisabled} onClick={props.onBuild}>创建导包任务</Button>
        )}
      </Space>
    </div>
  );
}
