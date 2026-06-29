import React from "react";
import { Button, Space, Spin, Tag } from "antd";
import { ResetConfirmModal, ResetOptionsPanel, ResetPreviewPanel } from "./components/EnvironmentResetPanels";
import { useEnvironmentReset } from "./hooks/useEnvironmentReset";
import styles from "./EnvironmentResetView.module.css";

export const EnvironmentResetView: React.FC = () => {
  const reset = useEnvironmentReset();

  return (
    <div className={styles.page}>
      <div className={styles.toolbar}>
        <div>
          <h3 className={styles.title}>环境清理</h3>
          <div className={styles.muted}>按范围预览并重置导包工厂元数据和包产物，默认保留系统设置。</div>
        </div>
        <Space wrap>
          <Tag color="blue">{reset.preview?.namespace || "deployment-package-factory"}</Tag>
          <Button icon={<i className="ri-search-eye-line" />} loading={reset.loading} onClick={() => void reset.runPreview()}>刷新预览</Button>
          <Button danger type="primary" icon={<i className="ri-delete-bin-6-line" />} disabled={!reset.preview || !reset.selectedKeys.length} onClick={() => reset.setConfirmOpen(true)}>
            执行清理
          </Button>
        </Space>
      </div>

      <div className={styles.layout}>
        <ResetOptionsPanel options={reset.options} onChange={reset.updateOption} />
        <Spin spinning={reset.loading}>
          <ResetPreviewPanel preview={reset.preview} />
        </Spin>
      </div>

      <ResetConfirmModal
        canExecute={reset.canExecute}
        confirmation={reset.confirmation}
        confirmationPhrase={reset.confirmationPhrase}
        executing={reset.executing}
        onCancel={() => reset.setConfirmOpen(false)}
        onChangeConfirmation={reset.setConfirmation}
        onExecute={() => void reset.executeReset()}
        open={reset.confirmOpen}
      />
    </div>
  );
};
