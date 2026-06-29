import React from "react";
import { App, Button, Form, Space, Spin, Tag, Upload } from "antd";
import type { UploadProps } from "antd";
import type { SystemSettings } from "../api/settings";
import { SystemSettingsForms } from "./components/SystemSettingsForms";
import { SystemSettingsNav } from "./components/SystemSettingsNav";
import { useSystemSettings } from "./hooks/useSystemSettings";
import styles from "./SystemSettingsView.module.css";

export const SystemSettingsView: React.FC = () => {
  const { message } = App.useApp();
  const [form] = Form.useForm<SystemSettings>();
  const state = useSystemSettings(form, (text) => message.error(text));

  const uploadProps: UploadProps = {
    accept: ".xlsx",
    maxCount: 1,
    showUploadList: false,
    beforeUpload: (file) => {
      void state.importWorkbook(file).then((result) => {
        if (result) message.success(`已导入 ${result.importedFields.length} 项环境配置`);
      });
      return Upload.LIST_IGNORE;
    },
  };

  return (
    <div className={styles.page}>
      <div className={styles.toolbar}>
        <div>
          <h3 className={styles.title}>系统设置</h3>
          <div className={styles.muted}>公共环境信息统一维护，导包和微服务注册自动复用。</div>
        </div>
        <Space wrap>
          {state.updatedAt ? <Tag color="blue">已更新 {state.updatedAt}</Tag> : null}
          <Upload {...uploadProps}>
            <Button icon={<i className="ri-file-excel-2-line" />} loading={state.importing}>导入环境 Excel</Button>
          </Upload>
          <Button icon={<i className="ri-refresh-line" />} onClick={() => void state.loadSettings()}>刷新</Button>
          <Button type="primary" icon={<i className="ri-save-3-line" />} loading={state.saving} onClick={() => void state.saveSettings().then((ok) => ok && message.success("系统设置已保存"))}>保存</Button>
        </Space>
      </div>

      <Spin spinning={state.loading}>
        <Form form={form} layout="vertical">
          <div className={styles.layout}>
            <SystemSettingsNav active={state.activeSection} onChange={state.setActiveSection} />
            <section className={styles.section}>
              <div className={styles.sectionHeader}>
                <h3 className={styles.sectionTitle}>当前分类配置</h3>
                {state.importedFields.length ? <Tag color="green">最近导入 {state.importedFields.length} 项</Tag> : null}
              </div>
              <SystemSettingsForms section={state.activeSection} />
            </section>
          </div>
        </Form>
      </Spin>
    </div>
  );
};
