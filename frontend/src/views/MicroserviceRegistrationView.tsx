import React from "react";
import { App, Button, Form, Space, Spin } from "antd";
import { listMicroservices } from "../api/microservices";
import { MicroserviceRegistrationWizard, stepFields } from "./components/MicroserviceRegistrationWizard";
import { MicroserviceResultPanel } from "./components/MicroserviceResultPanel";
import { RegisteredMicroservicesPanel } from "./components/RegisteredMicroservicesPanel";
import { DEFAULT_MICROSERVICE_VALUES, type MicroserviceWizardValues, useMicroserviceRegistration } from "./hooks/useMicroserviceRegistration";
import styles from "./MicroserviceRegistrationView.module.css";

export const MicroserviceRegistrationView: React.FC = () => {
  const { message } = App.useApp();
  const [form] = Form.useForm<MicroserviceWizardValues>();
  const state = useMicroserviceRegistration(form, (text) => message.error(text));

  const openWizard = () => {
    state.setCurrentStep(0);
    form.setFieldsValue(state.formValues);
    state.setWizardOpen(true);
  };

  const goNext = async () => {
    state.normalizeCurrentInputs();
    await form.validateFields(stepFields(state.currentStep));
    state.setFormValues(form.getFieldsValue(true));
    state.setCurrentStep(Math.min(state.currentStep + 1, 3));
  };

  const copyCommand = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      message.success("已复制");
    } catch {
      message.error("复制失败，请手动复制命令");
    }
  };

  const refreshServices = async () => {
    try {
      state.setRegisteredServices(await listMicroservices());
    } catch (error) {
      message.error(error instanceof Error ? error.message : "微服务列表刷新失败");
    }
  };

  return (
    <div className={styles.page}>
      <Spin spinning={state.loading}>
        <div className={styles.toolbar}>
          <div>
            <h3 className={styles.title}>微服务注册</h3>
            <div className={styles.muted}>通过向导生成项目骨架、部署脚本和流水线文件。</div>
          </div>
          <Space wrap>
            <Button icon={<i className="ri-refresh-line" />} onClick={() => void state.loadOptions()}>刷新</Button>
            <Button type="primary" icon={<i className="ri-add-circle-line" />} onClick={openWizard} disabled={!state.businessPlatforms.length}>注册微服务</Button>
          </Space>
        </div>
        <div className={styles.contentGrid}>
          <MicroserviceResultPanel result={state.result} retrying={state.retryingDelivery} refreshing={state.refreshingDelivery} onCopy={copyCommand} onRefreshDelivery={() => void state.refreshDeliveryStatus().then((ok) => ok && message.success("构建状态已刷新"))} onRetryDelivery={() => void state.retryDelivery().then((ok) => ok && message.success("交付已重试"))} />
          <RegisteredMicroservicesPanel services={state.registeredServices} onRefresh={() => void refreshServices()} />
        </div>
      </Spin>
      <MicroserviceRegistrationWizard
        businessPlatforms={state.businessPlatforms}
        currentStep={state.currentStep}
        deploymentOptions={state.deploymentOptions}
        form={form}
        formValues={state.formValues}
        open={state.wizardOpen}
        options={state.options}
        selectedPlatform={state.selectedPlatform}
        submitting={state.submitting}
        systemSettings={state.systemSettings}
        onClose={() => !state.submitting && state.setWizardOpen(false)}
        onNext={goNext}
        onPrevious={() => { state.setFormValues(form.getFieldsValue(true)); state.setCurrentStep(Math.max(state.currentStep - 1, 0)); }}
        onSubmit={() => void state.submit().then((ok) => ok && message.success("微服务项目已生成"))}
        onValuesChange={(_, values) => state.setFormValues({ ...DEFAULT_MICROSERVICE_VALUES, ...values })}
      />
    </div>
  );
};
