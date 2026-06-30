import { Button, Empty, Space, Tag } from "antd";
import type { DeploymentServiceOption, RegisteredDeploymentMicroservice } from "../../api/deploymentPackages";
import { microserviceDeliverySucceeded, selectedRegisteredMicroservices } from "./deploymentPackageUtils";
import styles from "../DeploymentPackageExportView.module.css";

interface Props {
  businessOptions: DeploymentServiceOption[];
  businessServices: string[];
  microservices: RegisteredDeploymentMicroservice[];
  refreshing: boolean;
  onRefresh: () => void;
}

export function MicroserviceDeliveryChecklist(props: Props) {
  const services = selectedRegisteredMicroservices(props.businessServices, props.businessOptions, props.microservices);
  return (
    <div className={styles.deliveryChecklist}>
      <div className={styles.panelTitleRow}>
        <h3 className={styles.sectionTitle}>微服务交付检查</h3>
        <Button size="small" icon={<i className="ri-refresh-line" />} loading={props.refreshing} disabled={!services.length} onClick={props.onRefresh}>刷新构建状态</Button>
      </div>
      {services.length ? <div className={styles.deliveryList}>{services.map((service) => <DeliveryItem key={service.projectId} service={service} />)}</div> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前业务平台暂无注册微服务" />}
    </div>
  );
}

function DeliveryItem({ service }: { service: RegisteredDeploymentMicroservice }) {
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
        {build?.url ? <Button size="small" href={build.url} target="_blank">Jenkins</Button> : null}
      </Space>
    </div>
  );
}
