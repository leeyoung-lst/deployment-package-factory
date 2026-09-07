import React from "react";
import styles from "../../MicroserviceRegistrationView.module.css";
import type { MicroserviceWizardStepProps } from "./types";

export function SummaryStep({ formValues, options, selectedPlatform, systemSettings }: MicroserviceWizardStepProps) {
  const microFrontend = options?.microFrontendFrameworks.find((item) => item.key === formValues.microFrontendFramework)?.name;
  const imageRegistry = formValues.imageRegistry || systemSettings?.harbor.registry || "未配置 Harbor";
  return (
    <div className={styles.summary}>
      <SummaryItem label="来源环境" value={formValues.sourceEnv} />
      <SummaryItem label="业务平台" value={selectedPlatform ? `${selectedPlatform.name} / ${selectedPlatform.namespace}` : formValues.businessPlatform} />
      <SummaryItem label="服务" value={`${formValues.serviceName} (${formValues.serviceKey})`} />
      <SummaryItem label="镜像" value={`${imageRegistry}/${formValues.imageNamespace}/${formValues.serviceKey}`} />
      <SummaryItem label="中间件" value={(formValues.middleware || []).join(", ") || "无"} />
      <SummaryItem label="MCP Server" value={formValues.mcpServerEnabled ? "启用" : "未启用"} />
      <SummaryItem label="微前端" value={microFrontend || "未启用"} />
      <SummaryItem label="K8s namespace" value={formValues.k8sNamespace || selectedPlatform?.namespace || "使用业务平台 namespace"} />
    </div>
  );
}

function SummaryItem({ label, value }: { label: string; value: string }) {
  return <div className={styles.summaryItem}><span className={styles.muted}>{label}</span><span className={styles.mono}>{value}</span></div>;
}
