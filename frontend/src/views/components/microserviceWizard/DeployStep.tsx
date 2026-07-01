import React from "react";
import { Form, Input, InputNumber } from "antd";
import { IMAGE_PATH_PATTERN, REGISTRY_HOST_PATTERN } from "../microserviceUtils";
import styles from "../../MicroserviceRegistrationView.module.css";
import type { MicroserviceWizardStepProps } from "./types";

export function DeployStep({ systemSettings }: MicroserviceWizardStepProps) {
  return (
    <div className={styles.stepGrid}>
      <div className={styles.fullWidth}><span className={styles.settingsHint}><i className="ri-settings-3-line" />默认读取系统设置：{systemSettings?.jenkins.baseUrl || "未配置 Jenkins"}</span></div>
      <Form.Item label="端口" name="port" rules={[{ required: true }]}><InputNumber min={1} max={65535} className={styles.fullControl} /></Form.Item>
      <Form.Item label="Git 分组" name="gitGroup" rules={[{ required: true }, { pattern: IMAGE_PATH_PATTERN, message: "仅支持小写路径片段" }]}><Input /></Form.Item>
      <Form.Item label="镜像仓库" name="imageRegistry" rules={[{ required: true }, { pattern: REGISTRY_HOST_PATTERN, message: "请输入仓库 Host" }]}><Input /></Form.Item>
      <Form.Item label="镜像命名空间" name="imageNamespace" rules={[{ required: true }, { pattern: IMAGE_PATH_PATTERN, message: "仅支持小写镜像路径片段" }]}><Input /></Form.Item>
    </div>
  );
}
