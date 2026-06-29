import React, { useEffect, useState } from "react";
import { App, Button, Checkbox, Form, Input, Space, Spin, Tag } from "antd";
import { getSystemSettings, updateSystemSettings, type SystemSettings } from "../api/settings";
import styles from "./SystemSettingsView.module.css";

const PATH_PATTERN = /^[a-z0-9]+(?:[._-][a-z0-9]+)*(?:\/[a-z0-9]+(?:[._-][a-z0-9]+)*)*$/;
const REGISTRY_HOST_PATTERN = /^[^\s/]+$/;

export const SystemSettingsView: React.FC = () => {
  const { message } = App.useApp();
  const [form] = Form.useForm<SystemSettings>();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [updatedAt, setUpdatedAt] = useState("");

  useEffect(() => {
    void loadSettings();
  }, []);

  const loadSettings = async () => {
    setLoading(true);
    try {
      const payload = await getSystemSettings();
      form.setFieldsValue(payload);
      setUpdatedAt(payload.updatedAt || "");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "系统设置加载失败");
    } finally {
      setLoading(false);
    }
  };

  const saveSettings = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      const payload = await updateSystemSettings(values);
      form.setFieldsValue(payload);
      setUpdatedAt(payload.updatedAt || "");
      message.success("系统设置已保存");
    } catch (error) {
      if (error instanceof Error) message.error(error.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className={styles.page}>
      <div className={styles.toolbar}>
        <div>
          <h3 className={styles.title}>系统设置</h3>
          <div className={styles.muted}>维护 Git、Harbor、Jenkins 等公共环境信息，业务页面自动复用这些默认值。</div>
        </div>
        <Space wrap>
          {updatedAt ? <Tag color="blue">已更新 {updatedAt}</Tag> : null}
          <Button icon={<i className="ri-refresh-line" />} onClick={() => void loadSettings()}>刷新</Button>
          <Button type="primary" icon={<i className="ri-save-3-line" />} loading={saving} onClick={() => void saveSettings()}>保存设置</Button>
        </Space>
      </div>

      <Spin spinning={loading}>
        <Form form={form} layout="vertical">
          <div className={styles.grid}>
            <section className={styles.section}>
              <h3 className={styles.sectionTitle}><i className="ri-git-branch-line" />Git</h3>
              <Form.Item label="Git 地址" name={["git", "baseUrl"]}>
                <Input placeholder="http://gitlab.local" />
              </Form.Item>
              <Form.Item
                label="默认分组"
                name={["git", "group"]}
                rules={[
                  { required: true, message: "请输入默认 Git 分组" },
                  { pattern: PATH_PATTERN, message: "仅支持小写路径片段，可用 / 分级" },
                ]}
              >
                <Input placeholder="business-services" />
              </Form.Item>
              <Form.Item label="用户名" name={["git", "username"]}>
                <Input placeholder="devops" />
              </Form.Item>
              <Form.Item label="邮箱" name={["git", "email"]}>
                <Input placeholder="devops@example.local" />
              </Form.Item>
            </section>

            <section className={styles.section}>
              <h3 className={styles.sectionTitle}><i className="ri-archive-drawer-line" />Harbor</h3>
              <Form.Item
                label="镜像仓库"
                name={["harbor", "registry"]}
                rules={[
                  { required: true, message: "请输入 Harbor 地址" },
                  { pattern: REGISTRY_HOST_PATTERN, message: "请输入仓库 Host，可带端口，不要包含路径" },
                ]}
              >
                <Input placeholder="harbor.local:5000" />
              </Form.Item>
              <Form.Item
                label="默认项目"
                name={["harbor", "project"]}
                rules={[
                  { required: true, message: "请输入 Harbor 项目" },
                  { pattern: PATH_PATTERN, message: "仅支持小写路径片段，可用 / 分级" },
                ]}
              >
                <Input placeholder="business" />
              </Form.Item>
              <Form.Item label="机器人账号" name={["harbor", "username"]}>
                <Input placeholder="robot$business" />
              </Form.Item>
              <Form.Item name={["harbor", "insecure"]} valuePropName="checked">
                <Checkbox>允许自签证书 / HTTP 仓库</Checkbox>
              </Form.Item>
            </section>

            <section className={styles.section}>
              <h3 className={styles.sectionTitle}><i className="ri-flow-chart" />Jenkins</h3>
              <Form.Item label="Jenkins 地址" name={["jenkins", "baseUrl"]}>
                <Input placeholder="http://jenkins.local" />
              </Form.Item>
              <Form.Item label="默认文件夹" name={["jenkins", "folder"]} rules={[{ pattern: PATH_PATTERN, message: "仅支持小写路径片段，可用 / 分级" }]}>
                <Input placeholder="business-services" />
              </Form.Item>
              <Form.Item label="用户名" name={["jenkins", "username"]}>
                <Input placeholder="jenkins" />
              </Form.Item>
            </section>
          </div>
        </Form>
      </Spin>
    </div>
  );
};
