import { Empty, Tag } from "antd";
import type { MicroserviceScaffoldResult } from "../../api/microservices";
import styles from "../MicroserviceRegistrationView.module.css";
import { MicroserviceResultContent } from "./MicroserviceResultContent";

export function MicroserviceResultPanel({ result, retrying, refreshing, onCopy, onRefreshDelivery, onRetryDelivery }: { result: MicroserviceScaffoldResult | null; retrying: boolean; refreshing: boolean; onCopy: (value: string) => void; onRefreshDelivery: () => void; onRetryDelivery: () => void }) {
  return (
    <section className={styles.panel}>
      <div className={styles.panelTitleRow}>
        <h3 className={styles.sectionTitle}>生成结果</h3>
        {result ? <Tag color="green">已生成</Tag> : null}
      </div>
      {result ? <MicroserviceResultContent result={result} retrying={retrying} refreshing={refreshing} onCopy={onCopy} onRefreshDelivery={onRefreshDelivery} onRetryDelivery={onRetryDelivery} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="点击注册微服务开始生成项目" />}
    </section>
  );
}
