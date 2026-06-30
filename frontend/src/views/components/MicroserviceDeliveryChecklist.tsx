import { Button, Empty, Space, Tag, Tooltip } from "antd";
import type { DeploymentServiceOption, RegisteredDeploymentMicroservice } from "../../api/deploymentPackages";
import { microserviceDeliverySucceeded, selectedRegisteredMicroservices } from "./deploymentPackageUtils";
import styles from "../DeploymentPackageExportView.module.css";

interface Props {
  businessOptions: DeploymentServiceOption[];
  businessServices: string[];
  microservices: RegisteredDeploymentMicroservice[];
  refreshing: boolean;
  retryingProjectId: string;
  onRefresh: () => void;
  onRetry: (projectId: string) => void;
}

export function MicroserviceDeliveryChecklist(props: Props) {
  const services = selectedRegisteredMicroservices(props.businessServices, props.businessOptions, props.microservices);
  return (
    <div className={styles.deliveryChecklist}>
      <div className={styles.panelTitleRow}>
        <h3 className={styles.sectionTitle}>微服务交付检查</h3>
        <Button size="small" icon={<i className="ri-refresh-line" />} loading={props.refreshing} disabled={!services.length} onClick={props.onRefresh}>刷新构建状态</Button>
      </div>
      {services.length ? <div className={styles.deliveryList}>{services.map((service) => <DeliveryItem key={service.projectId} retrying={props.retryingProjectId === service.projectId} service={service} onRetry={props.onRetry} />)}</div> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前业务平台暂无注册微服务" />}
    </div>
  );
}

function DeliveryItem({ service, retrying, onRetry }: { service: RegisteredDeploymentMicroservice; retrying: boolean; onRetry: (projectId: string) => void }) {
  const build = service.delivery?.build;
  const status = build?.status || service.delivery?.status || "unknown";
  const ready = microserviceDeliverySucceeded(service);
  return (
    <div className={styles.deliveryItem}>
      <div className={styles.deliveryMain}>
        <strong>{service.serviceName || service.serviceKey}</strong>
        <span className={styles.muted}>{service.serviceKey}</span>
      </div>
      <Space size={6} wrap>
        <Tag color={ready ? "success" : status === "running" ? "processing" : status === "failed" ? "error" : "warning"}>{ready ? "可导出" : status}</Tag>
        {build?.number ? <Tag>#{build.number}</Tag> : null}
        {service.cloneCommand ? <Tooltip title="复制 clone 命令"><Button size="small" icon={<i className="ri-file-copy-line" />} onClick={() => void navigator.clipboard.writeText(service.cloneCommand || "")} /></Tooltip> : null}
        {!ready ? <Button size="small" loading={retrying} onClick={() => onRetry(service.projectId)}>重试交付</Button> : null}
        {build?.url ? <Button size="small" href={build.url} target="_blank">Jenkins</Button> : null}
      </Space>
      {!ready ? <DeliverySteps service={service} /> : null}
    </div>
  );
}

function DeliverySteps({ service }: { service: RegisteredDeploymentMicroservice }) {
  const steps = service.delivery?.steps ?? [];
  if (!steps.length && !service.delivery?.build?.message) return null;
  return (
    <div className={styles.deliverySteps}>
      {steps.map((step) => <div className={styles.deliveryStep} key={`${step.name}-${step.action || ""}`}><Tag color={step.status === "success" ? "success" : step.status === "failed" ? "error" : "default"}>{step.status}</Tag><span>{step.name}</span><span className={styles.muted}>{step.message || step.hint || step.target}</span></div>)}
      {service.delivery?.build?.message ? <div className={styles.deliveryStep}><Tag color="warning">build</Tag><span>Jenkins</span><span className={styles.muted}>{service.delivery.build.message}</span></div> : null}
    </div>
  );
}
