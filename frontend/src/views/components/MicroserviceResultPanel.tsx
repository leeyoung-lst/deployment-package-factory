import React from "react";
import { Button, Empty, Input, Space, Tag } from "antd";
import { downloadMicroserviceScaffold, type MicroserviceScaffoldResult } from "../../api/microservices";
import styles from "../MicroserviceRegistrationView.module.css";

export function MicroserviceResultPanel({ result, onCopy }: { result: MicroserviceScaffoldResult | null; onCopy: (value: string) => void }) {
  return (
    <section className={styles.panel}>
      <div className={styles.panelTitleRow}>
        <h3 className={styles.sectionTitle}>生成结果</h3>
        {result ? <Tag color="green">已生成</Tag> : null}
      </div>
      {result ? <ResultContent result={result} onCopy={onCopy} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="点击注册微服务开始生成项目" />}
    </section>
  );
}

function ResultContent({ result, onCopy }: { result: MicroserviceScaffoldResult; onCopy: (value: string) => void }) {
  return (
    <div className={styles.resultGrid}>
      <ResultRow label="业务平台"><Space size={6} wrap><Tag color="purple">{result.businessPlatformName}</Tag><span className={styles.mono}>{result.businessPlatformNamespace}</span></Space></ResultRow>
      <ResultRow label="项目包"><span className={styles.mono}>{result.artifactName}</span></ResultRow>
      <ResultRow label="SHA256"><span className={styles.mono}>{result.sha256}</span></ResultRow>
      <ResultRow label="生成自检"><Tag color={result.validation.passed ? "green" : "red"}>{result.validation.passed ? "通过" : "未通过"}</Tag></ResultRow>
      <div className={styles.validationList}>{result.validation.checks.map((item) => <span key={item.name} className={item.passed ? styles.validationPassed : styles.validationFailed}><i className={item.passed ? "ri-checkbox-circle-line" : "ri-close-circle-line"} /><span>{item.message}</span></span>)}</div>
      <ResultRow label="本地初始化"><Space.Compact className={styles.commandBox}><Input className={styles.mono} value={result.cloneCommand} readOnly /><Button onClick={() => onCopy(result.cloneCommand)}>复制</Button></Space.Compact></ResultRow>
      <Space wrap><Button icon={<i className="ri-download-line" />} href={downloadMicroserviceScaffold(result.projectId)}>下载项目包</Button><Button icon={<i className="ri-file-copy-line" />} onClick={() => onCopy(result.downloadCommand)}>复制下载命令</Button></Space>
      <div className={styles.fileList}>{result.generatedFiles.map((item) => <span key={item} className={styles.mono}>{item}</span>)}</div>
    </div>
  );
}

function ResultRow({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className={styles.resultRow}><span className={styles.muted}>{label}</span><span>{children}</span></div>;
}
