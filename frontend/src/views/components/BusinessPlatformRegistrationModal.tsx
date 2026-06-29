import React from "react";
import { Form, Input, Modal, Radio } from "antd";
import type { FormInstance } from "antd";
import type { DeploymentPackageOptions } from "../../api/deploymentPackages";
import styles from "../DeploymentPackageExportView.module.css";

interface Props {
  form: FormInstance;
  loading: boolean;
  open: boolean;
  options: DeploymentPackageOptions | null;
  onCancel: () => void;
  onSubmit: () => void;
}

export function BusinessPlatformRegistrationModal({ form, loading, open, options, onCancel, onSubmit }: Props) {
  return (
    <Modal title="注册业务平台" open={open} onCancel={onCancel} onOk={onSubmit} confirmLoading={loading} okText="注册 namespace" cancelText="取消">
      <Form form={form} layout="vertical">
        <Form.Item label="环境" name="sourceEnv" rules={[{ required: true, message: "请选择环境" }]}>
          <Radio.Group>
            {(options?.sourceEnvs ?? ["dev", "test"]).map((env) => <Radio.Button key={env} value={env}>{env === "dev" ? "开发环境" : "测试环境"}</Radio.Button>)}
          </Radio.Group>
        </Form.Item>
        <div className={styles.split}>
          <Form.Item label="业务 Key" name="key" rules={[{ required: true, message: "请输入业务 Key" }]}><Input placeholder="eam / mes / erp" /></Form.Item>
          <Form.Item label="业务名称" name="name" rules={[{ required: true, message: "请输入业务名称" }]}><Input placeholder="EAM" /></Form.Item>
        </div>
        <Form.Item label="部署规格" name="profile"><Input placeholder="4x60 / 4x3，可选" /></Form.Item>
      </Form>
    </Modal>
  );
}
