import React from "react";
import { Form, Input, InputNumber } from "antd";
import { IMAGE_PATH_PATTERN } from "../microserviceUtils";
import styles from "../../MicroserviceRegistrationView.module.css";
import type { MicroserviceWizardStepProps } from "./types";

export function DeployStep({ systemSettings }: MicroserviceWizardStepProps) {
  const harborRegistry = systemSettings?.harbor.registry || "未配置 Harbor";

  return (
    <div className={styles.stepGrid}>
      <div className={styles.fullWidth}><span className={styles.settingsHint}><i className="ri-settings-3-line" />Harbor 来自系统设置：{harborRegistry}</span></div>
      <Form.Item label="端口" name="port" rules={[{ required: true }]}><InputNumber min={1} max={65535} className={styles.fullControl} /></Form.Item>
      <Form.Item label="Git 分组" name="gitGroup" rules={[{ required: true }, { pattern: IMAGE_PATH_PATTERN, message: "仅支持小写路径片段" }]}><Input /></Form.Item>
      <div><span className={styles.readonlyLabel}>镜像仓库</span><span className={styles.readonlyValue}>{harborRegistry}</span></div>
      <Form.Item label="镜像命名空间" name="imageNamespace" rules={[{ required: true }, { pattern: IMAGE_PATH_PATTERN, message: "仅支持小写镜像路径片段" }]}><Input /></Form.Item>
    </div>
  );
}
