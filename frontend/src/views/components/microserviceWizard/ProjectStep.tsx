import React from "react";
import { Form, Input } from "antd";
import { K8S_NAME_PATTERN } from "../microserviceUtils";
import styles from "../../MicroserviceRegistrationView.module.css";
import type { MicroserviceWizardStepProps } from "./types";

export function ProjectStep(_props: MicroserviceWizardStepProps) {
  return (
    <div className={styles.stepBody}>
      <Form.Item label="服务 Key" name="serviceKey" rules={[{ required: true }, { pattern: K8S_NAME_PATTERN, message: "仅支持小写字母、数字、中划线" }]}>
        <Input placeholder="460mes-service" />
      </Form.Item>
      <Form.Item label="服务名称" name="serviceName" rules={[{ required: true }]}>
        <Input placeholder="资产服务" />
      </Form.Item>
      <Form.Item label="描述" name="description">
        <Input.TextArea rows={3} />
      </Form.Item>
    </div>
  );
}
