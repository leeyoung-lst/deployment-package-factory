import React from "react";
import { Alert, Checkbox, Empty, Input, Modal, Space, Tag } from "antd";
import type {
  EnvironmentResetOptions,
  EnvironmentResetPreview,
  ResetPathSummary,
  ResetTableSummary,
} from "../../api/environmentReset";
import styles from "../EnvironmentResetView.module.css";

export const OPTION_LABELS: Record<keyof EnvironmentResetOptions, { label: string; description: string; danger?: boolean }> = {
  packageTasks: { label: "导包任务", description: "清空任务状态、日志和结果记录" },
  auditEvents: { label: "审计日志", description: "清空导包、下载、注册等操作审计" },
  businessPlatforms: { label: "业务平台注册", description: "清空导包工厂保存的业务平台注册信息" },
  microservices: { label: "微服务注册", description: "清空已注册微服务和项目下载记录" },
  packageArtifacts: { label: "部署包产物", description: "删除 artifacts 下已生成 tar.gz 与校验文件" },
  packageWorkDirs: { label: "工作目录", description: "删除 work 下导包中间目录" },
  systemSettings: { label: "系统设置", description: "清空 Git、Harbor、Jenkins 公共配置", danger: true },
};

const TABLE_NAMES: Record<string, string> = {
  packageTasks: "导包任务",
  auditEvents: "审计日志",
  businessPlatforms: "业务平台",
  microservices: "微服务",
  systemSettings: "系统设置",
};

const PATH_NAMES: Record<string, string> = {
  packageArtifacts: "部署包产物",
  packageWorkDirs: "工作目录",
};

export function ResetOptionsPanel({ options, onChange }: { options: EnvironmentResetOptions; onChange: (key: keyof EnvironmentResetOptions, checked: boolean) => void }) {
  return (
    <section className={styles.section}>
      <h3 className={styles.sectionTitle}><i className="ri-list-check-3" />清理范围</h3>
      <div className={styles.checks}>
        {(Object.keys(OPTION_LABELS) as Array<keyof EnvironmentResetOptions>).map((key) => (
          <Checkbox key={key} checked={options[key]} onChange={(event) => onChange(key, event.target.checked)}>
            <Space direction="vertical" size={0}>
              <span>{OPTION_LABELS[key].label}{OPTION_LABELS[key].danger ? <Tag color="red">谨慎</Tag> : null}</span>
              <span className={styles.muted}>{OPTION_LABELS[key].description}</span>
            </Space>
          </Checkbox>
        ))}
      </div>
      <Alert type="warning" showIcon message="执行前必须先看预览，并输入确认短语。清理不会删除导包工厂部署、PVC、PostgreSQL Pod 或业务命名空间。" />
    </section>
  );
}

export function ResetPreviewPanel({ preview }: { preview: EnvironmentResetPreview | null }) {
  if (!preview) {
    return (
      <section className={styles.section}>
        <h3 className={styles.sectionTitle}><i className="ri-dashboard-2-line" />预览摘要</h3>
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无清理预览" />
      </section>
    );
  }
  return (
    <section className={styles.section}>
      <h3 className={styles.sectionTitle}><i className="ri-dashboard-2-line" />预览摘要</h3>
      <div className={styles.summaryGrid}>
        <Metric label="选中数据行" value={`${preview.selectedRows}`} />
        <Metric label={preview.dryRun ? "预计文件" : "已删文件"} value={`${preview.dryRun ? preview.selectedFiles : preview.deletedFiles}`} />
        <Metric label={preview.dryRun ? "预计空间" : "释放空间"} value={formatBytes(preview.dryRun ? preview.selectedBytes : preview.freedBytes)} />
        <Metric label="模式" value={preview.dryRun ? "预览" : "已执行"} />
      </div>
      <div className={styles.detailGrid}>
        <DetailSection title="数据库表" items={preview.tables} renderItem={(item) => (
          <DetailRow key={item.name} label={TABLE_NAMES[item.name] || item.name} selected={item.selected} value={preview.dryRun ? `${item.existingRows} 行` : `删除 ${item.deletedRows} 行`} />
        )} />
        <DetailSection title="文件目录" items={preview.paths} renderItem={(item) => (
          <DetailRow key={item.name} label={PATH_NAMES[item.name] || item.name} selected={item.selected} value={preview.dryRun ? `${item.files} 个文件 / ${formatBytes(item.bytes)}` : `删除 ${item.deletedFiles} 个 / ${formatBytes(item.freedBytes)}`} extra={item.path} />
        )} />
      </div>
    </section>
  );
}

export function ResetConfirmModal(props: {
  canExecute: boolean;
  confirmation: string;
  confirmationPhrase: string;
  executing: boolean;
  onCancel: () => void;
  onChangeConfirmation: (value: string) => void;
  onExecute: () => void;
  open: boolean;
}) {
  return (
    <Modal title="确认环境清理" open={props.open} onCancel={props.onCancel} okText="确认清理" okButtonProps={{ danger: true, disabled: !props.canExecute, loading: props.executing }} onOk={props.onExecute} destroyOnClose>
      <div className={styles.dangerBox}>
        <Alert type="error" showIcon message="这是不可逆操作" description="选中的任务、审计、注册数据和包目录内容会被删除。系统设置只有勾选后才会清理。" />
        <div>
          <div className={styles.muted}>输入确认短语</div>
          <Input value={props.confirmation} onChange={(event) => props.onChangeConfirmation(event.target.value)} placeholder={props.confirmationPhrase} />
        </div>
      </div>
    </Modal>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className={styles.metric}>
      <span className={styles.muted}>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function DetailSection<T extends ResetTableSummary | ResetPathSummary>({ title, items, renderItem }: { title: string; items: T[]; renderItem: (item: T) => React.ReactNode }) {
  return (
    <section className={styles.detailList}>
      <h3 className={styles.sectionTitle}>{title}</h3>
      {items.map(renderItem)}
    </section>
  );
}

function DetailRow({ label, value, selected, extra }: { label: string; value: string; selected: boolean; extra?: string }) {
  return (
    <div className={styles.detailRow}>
      <div>
        <Space>
          <strong>{label}</strong>
          <Tag color={selected ? "red" : "default"}>{selected ? "选中" : "保留"}</Tag>
        </Space>
        {extra ? <div><code title={extra}>{extra}</code></div> : null}
      </div>
      <strong>{value}</strong>
    </div>
  );
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KiB`;
  if (value < 1024 * 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MiB`;
  return `${(value / 1024 / 1024 / 1024).toFixed(1)} GiB`;
}
