import React from "react";
import { Tag } from "antd";
import type { PackagePreview, ProjectProfile } from "../../api/deploymentPackages";
import { DependencyGraph } from "./DeploymentDependencyGraph";
import type { TargetDraft } from "./deploymentPackageUtils";
import styles from "../DeploymentPackageExportView.module.css";

export function PreviewSummary({ preview, project }: { preview: PackagePreview; project: ProjectProfile | null; targetProfile: TargetDraft }) {
  const groupedImageEntries = (preview.imageEntries ?? []).reduce<Record<string, PackagePreview["imageEntries"]>>((result, item) => {
    result[item.group] = result[item.group] || [];
    result[item.group].push(item);
    return result;
  }, {});
  return (
    <div className={styles.page}>
      <div className={styles.previewGrid}>
        <DependencyBlock title="基础平台" items={preview.platformServices} color="blue" />
        <DependencyBlock title="业务平台" items={preview.businessServices} color="purple" />
        <DependencyBlock title="中间件服务" items={preview.middleware} color="cyan" />
        <div className={styles.previewBlock}><h3>数据库二选一</h3><Tag color={preview.database.domestic ? "red" : "blue"}>{preview.database.name}</Tag><div className={`${styles.mono} ${styles.imageList}`}>{preview.database.image}</div></div>
      </div>
      <DependencyGraph preview={preview} />
      {preview.warnings.length ? <WarningBlock warnings={preview.warnings} /> : null}
      <ImageEntries groupedImageEntries={groupedImageEntries} />
      <OverlayBlock project={project} />
    </div>
  );
}

function WarningBlock({ warnings }: { warnings: string[] }) {
  return <div className={styles.previewBlock}><h3>提示</h3><div className={styles.tagList}>{warnings.map((warning) => <Tag key={warning} color="warning">{warning}</Tag>)}</div></div>;
}

function ImageEntries({ groupedImageEntries }: { groupedImageEntries: Record<string, PackagePreview["imageEntries"]> }) {
  return (
    <div className={styles.previewBlock}>
      <h3>镜像清单</h3>
      <div className={styles.imageList}>{Object.entries(groupedImageEntries).map(([group, images]) => <ImageGroup key={group} group={group} images={images} />)}</div>
    </div>
  );
}

function ImageGroup({ group, images }: { group: string; images: PackagePreview["imageEntries"] }) {
  return <div className={styles.imageGroup}><strong>{group}</strong><div className={styles.imageMapList}>{images.map((image) => <div className={`${styles.imageMapRow} ${image.sourceMissing ? styles.imageMapRowMissing : ""}`} key={`${group}-${image.targetRef}`}><span className={styles.mono}>{image.sourceRef}{image.sourceResolvedFrom === "kubernetes" ? <Tag color="green" style={{ marginLeft: 6 }}>K8s</Tag> : null}{image.sourceMissing ? <Tag color="red" style={{ marginLeft: 6 }}>未匹配</Tag> : null}{image.sourceMessage ? <span className={styles.imageMessage}>{image.sourceMessage}</span> : null}</span><i className="ri-arrow-right-line" /><span className={styles.mono}>{image.targetRef}</span></div>)}</div></div>;
}

function OverlayBlock({ project }: { project: ProjectProfile | null }) {
  return <div className={styles.previewBlock}><h3>项目 Overlay</h3><div className={styles.summaryRow}><span className={styles.muted}>输出目录</span><span className={styles.mono}>overlays/{project?.key || "custom"}</span></div><div className={styles.summaryRow}><span className={styles.muted}>产物</span><span className={styles.mono}>values.json / kustomization.yaml / README.md</span></div></div>;
}

function DependencyBlock({ title, items, color }: { title: string; items: PackagePreview["middleware"]; color: string }) {
  return <div className={styles.previewBlock}><h3>{title}</h3><div className={styles.tagList}>{items.length ? items.map((item) => <Tag key={item.key} color={item.locked ? color : "default"}>{item.name}</Tag>) : <Tag>未选择</Tag>}</div></div>;
}
