import React from "react";
import { Button, Checkbox, Empty, Form, Input, Radio, Select, Space, Tag } from "antd";
import type { CheckboxChangeEvent } from "antd/es/checkbox";
import type { DeployMode, DeploymentPackageOptions, DeploymentServiceOption, ImageExportEnvironmentCheck, PackagePreview, ProjectProfile, RegisteredDeploymentMicroservice, SourceEnv } from "../../api/deploymentPackages";
import { businessOptionValue, microserviceDeliverySummary, TargetDraft } from "./deploymentPackageUtils";
import { PreviewSnapshot } from "./DeploymentTaskPanels";
import { MicroserviceDeliveryChecklist } from "./MicroserviceDeliveryChecklist";
import styles from "../DeploymentPackageExportView.module.css";

export function ProductRangeStep(props: WizardStepProps) {
  const versions = props.options?.projects.find((item) => item.key === props.projectKey)?.versions ?? [];
  return <div className={styles.wizardSection}><h3 className={styles.sectionTitle}>产品范围</h3><div className={styles.split}><Form.Item label="项目"><Select value={props.projectKey} options={(props.options?.projects ?? []).map((item) => ({ value: item.key, label: item.name }))} onChange={props.onProjectChange} placeholder="暂无真实项目" disabled={!props.options?.projects.length} /></Form.Item><Form.Item label="产品版本"><Select value={props.productVersion} options={versions.map((item) => ({ value: item, label: item }))} onChange={props.onProductVersionChange} placeholder="暂无真实版本" disabled={!versions.length} /></Form.Item></div><ProjectSummary project={props.selectedProject} /><div className={styles.split}><Form.Item label="来源环境"><Radio.Group value={props.sourceEnv} onChange={(event) => props.onSourceEnvChange(event.target.value)}>{(props.options?.sourceEnvs ?? []).map((env) => <Radio.Button key={env} value={env}>{env === "dev" ? "开发环境" : "测试环境"}</Radio.Button>)}</Radio.Group>{props.options?.sourceEnvs.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无可读取的来源环境" /> : null}</Form.Item><Form.Item label="部署方式"><Radio.Group value={props.deployMode} onChange={(event) => props.onDeployModeChange(event.target.value)}><Space direction="vertical">{(props.options?.deployModes ?? ["k8s", "docker-compose"]).map((mode) => <Radio key={mode} value={mode}>{mode === "k8s" ? "Kubernetes" : "Docker Compose"}</Radio>)}</Space></Radio.Group></Form.Item></div></div>;
}

export function PlatformServicesStep(props: WizardStepProps) {
  return <div className={styles.wizardGrid}><ServiceGroup title="业务平台服务" items={props.businessOptionsForSourceEnv} value={props.businessServices} icon="ri-apps-2-line" empty="当前来源环境暂无已注册业务平台" onChange={props.onBusinessChange} microservices={props.options?.microservices ?? []} /><ServiceGroup title="基础平台服务" items={props.platformOptionsForSourceEnv} value={props.platformServices} icon="ri-server-line" empty="当前来源环境暂无真实基础平台服务" onChange={props.onPlatformChange} onRequiredPlatformClick={props.onRequiredPlatformClick} /></div>;
}

export function MiddlewareImageStep(props: WizardStepProps) {
  return <div className={styles.wizardGrid}><div className={styles.wizardSection}><h3 className={styles.sectionTitle}>中间件服务</h3><Form.Item label="数据库中间件（二选一）"><Radio.Group value={props.database} onChange={(event) => props.onDatabaseChange(event.target.value)}><Space direction="vertical">{props.databaseOptionsForSourceEnv.map((item) => <Radio key={item.key} value={item.key}>{item.name}<Tag color={item.domestic ? "red" : "blue"} style={{ marginLeft: 8 }}>{item.domestic ? "国产化" : "非国产化"}</Tag></Radio>)}</Space></Radio.Group>{props.databaseOptionsForSourceEnv.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前来源环境暂无真实数据库服务" /> : null}</Form.Item></div><div className={styles.wizardSection}><h3 className={styles.sectionTitle}>镜像导出</h3><Form.Item label="镜像模式" name="imageMode"><Select options={[{ value: "image-archive", label: "镜像归档：导出离线镜像 tar" }, { value: "image-manifest", label: "镜像清单：仅生成 pull/save/load 脚本" }]} /></Form.Item><ImageEnvironmentStatus value={props.imageEnvironment} loading={props.imageEnvironmentLoading} /></div></div>;
}

export function TargetProfileStep() {
  return <div className={styles.wizardSection}><h3 className={styles.sectionTitle}>生产目标</h3><div className={styles.split}><Form.Item label="目标环境" name="env" rules={[{ required: true, message: "请输入目标环境" }]}><Input /></Form.Item><Form.Item label="命名空间前缀" name="namespacePrefix" rules={[{ required: true, message: "请输入命名空间前缀" }]}><Input /></Form.Item><Form.Item label="域名" name="domain" rules={[{ required: true, message: "请输入生产域名" }]}><Input /></Form.Item><Form.Item label="源镜像仓库" name="sourceRegistry"><Input placeholder="可选，导包时从该仓库拉取镜像" /></Form.Item><Form.Item name="sourceRegistryInsecure" valuePropName="checked"><Checkbox>源仓库使用自签证书</Checkbox></Form.Item><Form.Item label="镜像仓库" name="registry"><Input placeholder="生产部署目标镜像仓库" /></Form.Item><Form.Item label="StorageClass" name="storageClass"><Input placeholder="留空使用集群默认值" /></Form.Item></div></div>;
}

export function ConfirmStep(props: WizardStepProps) {
  return <div className={styles.wizardGrid}><div className={styles.wizardSection}><h3 className={styles.sectionTitle}>导包确认</h3><div className={styles.draftGrid}><DraftItem label="项目" value={props.selectedProject?.name || props.projectKey || "未选择"} /><DraftItem label="版本" value={props.productVersion || "未选择"} /><DraftItem label="来源环境" value={props.sourceEnv === "dev" ? "开发环境" : "测试环境"} /><DraftItem label="部署方式" value={props.deployMode === "k8s" ? "Kubernetes" : "Docker Compose"} /><DraftItem label="业务平台" value={props.selectedBusinessOptions.map((item) => item.name).join("、") || "未选择"} /><DraftItem label="基础平台" value={props.selectedPlatformOptions.map((item) => item.name).join("、") || "未选择"} /><DraftItem label="数据库" value={props.selectedDatabaseOption?.name || props.database || "未选择"} /><DraftItem label="镜像模式" value={props.targetDraft.imageMode === "image-manifest" ? "镜像清单" : "镜像归档"} /><DraftItem label="目标环境" value={props.targetDraft.env || "-"} /><DraftItem label="目标域名" value={props.targetDraft.domain || "-"} /><DraftItem label="命名空间" value={props.targetDraft.namespacePrefix || "-"} /><DraftItem label="StorageClass" value={props.targetDraft.storageClass || "集群默认"} /></div><MicroserviceDeliveryChecklist businessOptions={props.businessOptionsForSourceEnv} businessServices={props.businessServices} microservices={props.options?.microservices ?? []} refreshing={props.refreshingMicroservices} retryingProjectId={props.retryingMicroserviceId} onRefresh={props.onRefreshMicroservices} onRetry={props.onRetryMicroservice} /></div><div className={styles.wizardSection}><div className={styles.panelTitleRow}><h3 className={styles.sectionTitle}>预览摘要</h3><Button size="small" icon={<i className="ri-refresh-line" />} loading={props.previewing} onClick={props.onRefreshPreview}>刷新</Button></div>{props.preview ? <PreviewSnapshot preview={props.preview} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无预览" />}</div></div>;
}

function ServiceGroup({ title, items, value, icon, empty, onChange, onRequiredPlatformClick, microservices = [] }: { title: string; items: DeploymentServiceOption[]; value: string[]; icon: string; empty: string; onChange: (values: Array<string | number | boolean>) => void; onRequiredPlatformClick?: (event: CheckboxChangeEvent) => void; microservices?: RegisteredDeploymentMicroservice[] }) {
  const isBusiness = title.startsWith("业务");
  return <div className={styles.wizardSection}><h3 className={styles.sectionTitle}>{title}</h3><Checkbox.Group className={styles.serviceGrid} value={value} onChange={onChange}>{items.map((item) => { const summary = isBusiness ? microserviceDeliverySummary(item, microservices) : null; return <Checkbox key={`${item.sourceEnv}-${item.key}-${item.profile || "default"}`} value={isBusiness ? businessOptionValue(item) : item.key} disabled={item.required} onChange={item.required ? onRequiredPlatformClick : undefined}><span className={styles.serviceItem}><span className={styles.serviceMain}><i className={icon} /><span className={styles.serviceName}>{item.name}</span>{summary ? <Tag color={summary.color}>{summary.label}</Tag> : null}</span><span className={styles.muted}>{item.required ? "必选" : item.namespace || item.profile || item.namespaceGroup}</span></span></Checkbox>; })}</Checkbox.Group>{items.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={empty} /> : null}</div>;
}

export function DraftItem({ label, value }: { label: string; value: React.ReactNode }) {
  return <div className={styles.draftItem}><span className={styles.muted}>{label}</span><strong>{value}</strong></div>;
}

function ProjectSummary({ project }: { project: ProjectProfile | null }) {
  if (!project) return <div className={styles.projectSummary}><span className={styles.muted}>未选择项目模板</span></div>;
  return <div className={styles.projectSummary}><div className={styles.summaryRow}><span className={styles.muted}>镜像 Tag</span><Tag color="geekblue">{project.imageTag || "prod"}</Tag></div><div className={styles.summaryRow}><span className={styles.muted}>Overlay</span><div className={styles.tagList}>{project.overlays.length ? project.overlays.map((item) => <Tag key={item}>{item}</Tag>) : <Tag>默认</Tag>}</div></div><div className={styles.summaryRow}><span className={styles.muted}>目标配置</span><span className={styles.mono}>{project.namespacePrefix} / {project.domain} / {project.storageClass || "default-storage"}</span></div></div>;
}

function ImageEnvironmentStatus({ value, loading }: { value: ImageExportEnvironmentCheck | null; loading: boolean }) {
  const color = value?.available ? "green" : "orange";
  const label = value?.available ? "导出工具可用" : "导出工具不可用";
  return <div className={styles.imageEnvironment}><Space size={8} wrap><Tag color={loading ? "processing" : color}>{loading ? "检查中" : label}</Tag>{value?.exportTool ? <Tag>{value.exportTool}</Tag> : null}{value?.toolVersion || value?.dockerVersion ? <span className={styles.mono}>{value.toolVersion || value.dockerVersion}</span> : null}</Space><span className={styles.muted}>{value?.message || "镜像归档模式需要导包 worker 可访问镜像仓库，并具备 skopeo 或 Docker CLI 导出能力。"}</span></div>;
}

export interface WizardStepProps {
  businessOptionsForSourceEnv: DeploymentServiceOption[];
  businessServices: string[];
  database: string;
  databaseOptionsForSourceEnv: Array<{ key: string; name: string; domestic: boolean }>;
  deployMode: DeployMode;
  imageEnvironment: ImageExportEnvironmentCheck | null;
  imageEnvironmentLoading: boolean;
  options: DeploymentPackageOptions | null;
  platformOptionsForSourceEnv: DeploymentServiceOption[];
  platformServices: string[];
  preview: PackagePreview | null;
  previewing: boolean;
  productVersion: string;
  projectKey: string;
  selectedBusinessOptions: DeploymentServiceOption[];
  selectedDatabaseOption: { name: string } | null;
  selectedPlatformOptions: DeploymentServiceOption[];
  selectedProject: ProjectProfile | null;
  sourceEnv: SourceEnv;
  targetDraft: TargetDraft;
  onBusinessChange: (values: Array<string | number | boolean>) => void;
  onDatabaseChange: (value: string) => void;
  onDeployModeChange: (value: DeployMode) => void;
  onPlatformChange: (values: Array<string | number | boolean>) => void;
  onProductVersionChange: (value: string) => void;
  onProjectChange: (value: string) => void;
  onRefreshMicroservices: () => void;
  onRefreshPreview: () => void;
  onRequiredPlatformClick: (event: CheckboxChangeEvent) => void;
  onRetryMicroservice: (projectId: string) => void;
  onSourceEnvChange: (value: SourceEnv) => void;
  refreshingMicroservices: boolean;
  retryingMicroserviceId: string;
}
