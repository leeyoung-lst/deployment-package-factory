import React from "react";
import { Form, Select } from "antd";
import type { SourceEnv } from "../../../api/deploymentPackages";
import { businessPlatformValue } from "../microserviceUtils";
import styles from "../../MicroserviceRegistrationView.module.css";
import type { MicroserviceWizardStepProps } from "./types";

export function PlatformStep({ businessPlatforms, deploymentOptions, form, onValuesChange }: MicroserviceWizardStepProps) {
  const selectPlatform = (value: SourceEnv) => {
    const first = (deploymentOptions?.businessServices ?? []).find((item) => item.registered && item.status !== "disabled" && item.sourceEnv === value);
    form.setFieldsValue({ businessPlatform: first ? businessPlatformValue(first) : "", k8sNamespace: first?.namespace || "" });
    onValuesChange(null, form.getFieldsValue(true));
  };

  return (
    <div className={styles.stepBody}>
      <Form.Item label="来源环境" name="sourceEnv" rules={[{ required: true, message: "请选择来源环境" }]}>
        <Select options={(deploymentOptions?.sourceEnvs ?? ["test"]).map((item) => ({ value: item, label: item === "dev" ? "开发环境" : "测试环境" }))} onChange={selectPlatform} />
      </Form.Item>
      <Form.Item label="业务平台" name="businessPlatform" rules={[{ required: true, message: "请选择业务平台" }]}>
        <Select
          placeholder="请先注册业务平台"
          options={businessPlatforms.map((item) => ({ value: businessPlatformValue(item), label: `${item.name} / ${item.namespace || item.profile || item.key}` }))}
          onChange={() => {
            const selected = businessPlatforms.find((item) => businessPlatformValue(item) === form.getFieldValue("businessPlatform"));
            form.setFieldValue("k8sNamespace", selected?.namespace || "");
            onValuesChange(null, form.getFieldsValue(true));
          }}
        />
      </Form.Item>
    </div>
  );
}
