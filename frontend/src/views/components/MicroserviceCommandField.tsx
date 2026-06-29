import { Button, Input, Space } from "antd";
import styles from "../MicroserviceRegistrationView.module.css";

export function MicroserviceCommandField({ value, onCopy }: { value: string; onCopy: (value: string) => void }) {
  return (
    <Space.Compact className={styles.commandBox}>
      <Input className={styles.mono} value={value} readOnly />
      <Button onClick={() => onCopy(value)}>复制</Button>
    </Space.Compact>
  );
}
