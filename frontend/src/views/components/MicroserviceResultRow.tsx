import React from "react";
import styles from "../MicroserviceRegistrationView.module.css";

export function MicroserviceResultRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className={styles.resultRow}>
      <span className={styles.muted}>{label}</span>
      <span>{children}</span>
    </div>
  );
}
