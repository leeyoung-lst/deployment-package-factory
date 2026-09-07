import React from "react";
import { Checkbox, Form, Input } from "antd";
import styles from "../../MicroserviceRegistrationView.module.css";
import type { MicroserviceWizardStepProps } from "./types";

export function DependencyStep({ form, options, selectedPlatform }: MicroserviceWizardStepProps) {
  const backendSelected = Form.useWatch("projectKind", form) !== "frontend";
  const mcpFeature = (options?.features ?? []).find((item) => item.field === "mcpServerEnabled");
  return (
    <div className={styles.stepBody}>
      <div>
        <span className={styles.readonlyLabel}>K8s namespace</span>
        <span className={styles.readonlyValue}>{selectedPlatform?.namespace || "请先选择业务平台"}</span>
      </div>
      <Form.Item name="k8sNamespace" hidden>
        <Input />
      </Form.Item>
      <Form.Item label="中间件" name="middleware">
        <Checkbox.Group options={(options?.middleware ?? []).map((item) => ({ value: item.key, label: item.name }))} />
      </Form.Item>
      {backendSelected && (!mcpFeature || mcpFeature.projectKinds.includes("backend")) ? (
        <Form.Item label="MCP Server" name="mcpServerEnabled" valuePropName="checked">
          <Checkbox>{mcpFeature?.description || "支持 MCP Server，生成示例项目和配置"}</Checkbox>
        </Form.Item>
      ) : null}
    </div>
  );
}
