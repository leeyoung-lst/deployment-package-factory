import { Tag } from "antd";
import type { MicroserviceScaffoldResult } from "../../api/microservices";
import styles from "../MicroserviceRegistrationView.module.css";

const STATUS_COLOR: Record<string, string> = {
  ready: "green",
  pending: "orange",
  failed: "red",
  skipped: "default",
};

export function MicroserviceDeliveryDiagnostics({ delivery }: { delivery: MicroserviceScaffoldResult["delivery"] }) {
  return (
    <div className={styles.deliveryDiagnostics}>
      {delivery.steps.map((step) => (
        <section key={step.name} className={styles.deliveryStep}>
          <div className={styles.deliveryStepHeader}>
            <strong>{step.action || step.name}</strong>
            <Tag color={STATUS_COLOR[step.status] || "default"}>{step.status}</Tag>
          </div>
          <span className={styles.muted}>{step.phase} · {step.elapsedMs}ms{step.retryable ? " · 可重试" : ""}</span>
          {step.target ? <span className={styles.mono}>{step.target}</span> : null}
          <span>{step.message}</span>
          {step.hint ? <span className={styles.deliveryHint}>{step.hint}</span> : null}
        </section>
      ))}
    </div>
  );
}
