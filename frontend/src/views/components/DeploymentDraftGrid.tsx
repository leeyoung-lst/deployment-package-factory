import React from "react";
import type { DeploymentServiceOption, ProjectProfile, SourceEnv } from "../../api/deploymentPackages";
import { DraftItem } from "./DeploymentPackageWizardSteps";
import type { TargetDraft } from "./deploymentPackageUtils";
import styles from "../DeploymentPackageExportView.module.css";

interface Props {
  database: string;
  deployMode: string;
  productVersion: string;
  projectKey: string;
  selectedBusinessOptions: DeploymentServiceOption[];
  selectedDatabaseName?: string;
  selectedPlatformOptions: DeploymentServiceOption[];
  selectedProject: ProjectProfile | null;
  sourceEnv: SourceEnv;
  targetDraft: TargetDraft;
}

export function DeploymentDraftGrid(props: Props) {
  return (
    <div className={styles.draftGrid}>
      <DraftItem label="项目" value={props.selectedProject?.name || props.projectKey || "未选择"} />
      <DraftItem label="版本" value={props.productVersion || "未选择"} />
      <DraftItem label="来源" value={props.sourceEnv === "dev" ? "开发环境" : "测试环境"} />
      <DraftItem label="部署" value={props.deployMode === "k8s" ? "Kubernetes" : "Docker Compose"} />
      <DraftItem label="业务平台" value={`${props.selectedBusinessOptions.length} 个`} />
      <DraftItem label="基础平台" value={`${props.selectedPlatformOptions.length} 个`} />
      <DraftItem label="数据库" value={props.selectedDatabaseName || props.database || "未选择"} />
      <DraftItem label="目标" value={`${props.targetDraft.namespacePrefix || "-"} / ${props.targetDraft.domain || "-"}`} />
    </div>
  );
}
