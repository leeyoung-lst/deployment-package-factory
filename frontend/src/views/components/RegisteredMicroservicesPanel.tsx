import React from "react";
import { Button, Empty, Tag } from "antd";
import type { RegisteredMicroservice } from "../../api/microservices";
import styles from "../MicroserviceRegistrationView.module.css";

export function RegisteredMicroservicesPanel({ services, onRefresh }: { services: RegisteredMicroservice[]; onRefresh: () => void }) {
  return (
    <section className={styles.panel}>
      <div className={styles.panelTitleRow}>
        <h3 className={styles.sectionTitle}>已注册微服务</h3>
        <Button size="small" icon={<i className="ri-refresh-line" />} onClick={onRefresh}>刷新列表</Button>
      </div>
      {services.length ? <div className={styles.serviceList}>{services.map((item) => <ServiceItem key={`${item.sourceEnv}-${item.businessPlatformKey}-${item.businessPlatformProfile}-${item.serviceKey}`} item={item} />)}</div> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无已注册微服务" />}
    </section>
  );
}

function ServiceItem({ item }: { item: RegisteredMicroservice }) {
  return (
    <div className={styles.serviceItem}>
      <span><strong>{item.serviceName}</strong><span className={styles.mono}>{item.serviceKey}</span></span>
      <span><Tag color="purple">{item.businessPlatformName}</Tag><Tag color="blue">{item.sourceEnv}</Tag></span>
      <span className={styles.mono}>{item.image}</span>
    </div>
  );
}
