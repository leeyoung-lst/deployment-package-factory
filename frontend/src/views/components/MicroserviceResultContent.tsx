import { Button, Space, Tag } from "antd";
import { downloadMicroserviceScaffold, type MicroserviceScaffoldResult } from "../../api/microservices";
import styles from "../MicroserviceRegistrationView.module.css";
import { MicroserviceCommandField } from "./MicroserviceCommandField";
import { MicroserviceDeliveryDiagnostics } from "./MicroserviceDeliveryDiagnostics";
import { MicroserviceResultRow } from "./MicroserviceResultRow";

export function MicroserviceResultContent({ result, retrying, refreshing, onCopy, onRefreshDelivery, onRetryDelivery }: { result: MicroserviceScaffoldResult; retrying: boolean; refreshing: boolean; onCopy: (value: string) => void; onRefreshDelivery: () => void; onRetryDelivery: () => void }) {
  const agentConfig = JSON.stringify(mcpAgentConfig(result), null, 2);
  return (
    <div className={styles.resultGrid}>
      <MicroserviceResultRow label="业务平台"><Space size={6} wrap><Tag color="purple">{result.businessPlatformName}</Tag><span className={styles.mono}>{result.businessPlatformNamespace}</span></Space></MicroserviceResultRow>
      <MicroserviceResultRow label="项目类型"><Space size={6} wrap><Tag color="blue">{result.projectKind}</Tag><Tag>{result.techStack}</Tag>{result.microFrontendFramework ? <Tag color="cyan">{result.microFrontendFramework}</Tag> : null}</Space></MicroserviceResultRow>
      {result.mcpServerEnabled ? <MicroserviceResultRow label="MCP"><Space size={6} wrap><Tag color="green">{result.mcpTransport || "streamable-http"}</Tag><Tag color={result.mcpRequiresApiKey ? "orange" : "default"}>{result.mcpRequiresApiKey ? "Bearer API Key" : "未启用鉴权"}</Tag><span className={styles.mono}>{result.mcpEndpoint || "/mcp"}</span></Space></MicroserviceResultRow> : null}
      {result.mcpServerEnabled ? <MicroserviceResultRow label="Agent地址"><MicroserviceCommandField value={result.mcpServiceUrl || `http://${result.serviceKey}.${result.businessPlatformNamespace}.svc.cluster.local/mcp`} onCopy={onCopy} /></MicroserviceResultRow> : null}
      <MicroserviceResultRow label="镜像"><span className={styles.mono}>{result.image}</span></MicroserviceResultRow>
      <MicroserviceResultRow label="Git项目"><span className={styles.mono}>{result.gitRepositoryUrl}</span></MicroserviceResultRow>
      <MicroserviceResultRow label="Jenkins"><span className={styles.mono}>{result.jenkinsJob}</span></MicroserviceResultRow>
      <MicroserviceResultRow label="项目包"><Space size={6} wrap><span className={styles.mono}>{result.artifactName}</span><Tag color={result.artifactAvailable ? "green" : "default"}>{result.artifactAvailable ? "可下载" : "已清理"}</Tag></Space></MicroserviceResultRow>
      <MicroserviceResultRow label="生成自检"><Tag color={result.validation.passed ? "green" : "red"}>{result.validation.passed ? "通过" : "未通过"}</Tag></MicroserviceResultRow>
      <div className={styles.validationList}>{result.validation.checks.map((item) => <span key={item.name} className={item.passed ? styles.validationPassed : styles.validationFailed}><i className={item.passed ? "ri-checkbox-circle-line" : "ri-close-circle-line"} /><span>{item.message}</span></span>)}</div>
      <MicroserviceResultRow label="交付准备"><Space wrap><Tag color={result.delivery.status === "success" ? "green" : result.delivery.status === "ready" ? "blue" : result.delivery.status === "running" ? "processing" : result.delivery.status === "pending" ? "orange" : result.delivery.status === "failed" ? "red" : "default"}>{result.delivery.status}</Tag><Button size="small" loading={refreshing} onClick={onRefreshDelivery}>刷新构建</Button>{result.delivery.steps.some((step) => step.retryable) ? <Button size="small" loading={retrying} onClick={onRetryDelivery}>重试交付</Button> : null}</Space></MicroserviceResultRow>
      <MicroserviceDeliveryDiagnostics delivery={result.delivery} />
      <MicroserviceResultRow label="本地初始化"><MicroserviceCommandField value={result.cloneCommand} onCopy={onCopy} /></MicroserviceResultRow>
      <MicroserviceResultRow label="构建镜像"><MicroserviceCommandField value={result.buildCommand} onCopy={onCopy} /></MicroserviceResultRow>
      <MicroserviceResultRow label="部署验证"><MicroserviceCommandField value={result.deployCommand} onCopy={onCopy} /></MicroserviceResultRow>
      {result.artifactAvailable ? <Space wrap><Button icon={<i className="ri-download-line" />} href={downloadMicroserviceScaffold(result.projectId)}>下载项目包</Button><Button icon={<i className="ri-file-copy-line" />} onClick={() => onCopy(result.downloadCommand)}>复制下载命令</Button>{result.mcpServerEnabled ? <Button icon={<i className="ri-file-copy-line" />} onClick={() => onCopy(agentConfig)}>复制Agent MCP配置</Button> : null}</Space> : null}
      <div className={styles.fileList}>{result.generatedFiles.map((item) => <span key={item} className={styles.mono}>{item}</span>)}</div>
    </div>
  );
}

function mcpAgentConfig(result: MicroserviceScaffoldResult) {
  if (Object.keys(result.mcpAgentConfig || {}).length) return result.mcpAgentConfig;
  return {
    type: result.mcpTransport || "streamable-http",
    url: result.mcpServiceUrl || `http://${result.serviceKey}.${result.businessPlatformNamespace}.svc.cluster.local/mcp`,
    headers: result.mcpRequiresApiKey ? { Authorization: "Bearer ${MCP_API_KEY}" } : {},
  };
}
