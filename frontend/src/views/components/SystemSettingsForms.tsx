import React from "react";
import { Checkbox, Form, Input, InputNumber, Switch } from "antd";
import type { SettingsSection } from "../hooks/useSystemSettings";
import styles from "../SystemSettingsView.module.css";

const PATH_PATTERN = /^[a-z0-9]+(?:[._-][a-z0-9]+)*(?:\/[a-z0-9]+(?:[._-][a-z0-9]+)*)*$/;
const REGISTRY_HOST_PATTERN = /^[^\s/]+$/;
const MIDDLEWARE = ["redis", "postgresql", "dm", "iotdb", "mongodb", "kafka", "mq", "nacos"];

export function SystemSettingsForms({ section }: { section: SettingsSection }) {
  if (section === "git") return <GitSettingsForm />;
  if (section === "harbor") return <HarborSettingsForm />;
  if (section === "jenkins") return <JenkinsSettingsForm />;
  if (section === "kubernetes") return <KubernetesSettingsForm />;
  return <MiddlewareSettingsForm />;
}

function GitSettingsForm() {
  return (
    <div className={styles.formGrid}>
      <Form.Item label="Git 地址" name={["git", "baseUrl"]}><Input placeholder="http://gitlab.local" /></Form.Item>
      <Form.Item label="默认分组" name={["git", "group"]} rules={[{ required: true }, { pattern: PATH_PATTERN, message: "仅支持小写路径片段" }]}><Input /></Form.Item>
      <Form.Item label="用户名" name={["git", "username"]}><Input /></Form.Item>
      <Form.Item label="邮箱" name={["git", "email"]}><Input /></Form.Item>
    </div>
  );
}

function HarborSettingsForm() {
  return (
    <div className={styles.formGrid}>
      <Form.Item label="镜像仓库" name={["harbor", "registry"]} rules={[{ required: true }, { pattern: REGISTRY_HOST_PATTERN, message: "请输入 Host，可带端口" }]}><Input /></Form.Item>
      <Form.Item label="默认项目" name={["harbor", "project"]} rules={[{ required: true }, { pattern: PATH_PATTERN, message: "仅支持小写路径片段" }]}><Input /></Form.Item>
      <Form.Item label="机器人账号" name={["harbor", "username"]}><Input /></Form.Item>
      <Form.Item label="机器人密码" name={["harbor", "password"]}><Input.Password /></Form.Item>
      <Form.Item name={["harbor", "insecure"]} valuePropName="checked"><Checkbox>允许自签证书 / HTTP 仓库</Checkbox></Form.Item>
    </div>
  );
}

function JenkinsSettingsForm() {
  return (
    <div className={styles.formGrid}>
      <Form.Item label="Jenkins 地址" name={["jenkins", "baseUrl"]}><Input /></Form.Item>
      <Form.Item label="默认文件夹" name={["jenkins", "folder"]} rules={[{ pattern: PATH_PATTERN, message: "仅支持小写路径片段" }]}><Input /></Form.Item>
      <Form.Item label="用户名" name={["jenkins", "username"]}><Input /></Form.Item>
      <Form.Item label="密码 / Token" name={["jenkins", "password"]}><Input.Password /></Form.Item>
      <Form.Item label="部署 Job" name={["jenkins", "deployJob"]}><Input /></Form.Item>
      <Form.Item label="镜像凭据 ID" name={["jenkins", "registryCredentialId"]}><Input /></Form.Item>
      <Form.Item label="Kubeconfig 凭据 ID" name={["jenkins", "kubeconfigCredentialId"]}><Input /></Form.Item>
    </div>
  );
}

function KubernetesSettingsForm() {
  return (
    <div className={styles.formGrid}>
      <Form.Item label="集群名称" name={["kubernetes", "clusterName"]}><Input /></Form.Item>
      <Form.Item label="Ingress VIP" name={["kubernetes", "ingressVip"]}><Input /></Form.Item>
      <Form.Item label="导包工厂 Namespace" name={["kubernetes", "factoryNamespace"]}><Input /></Form.Item>
      <Form.Item label="默认 Namespace" name={["kubernetes", "defaultNamespace"]}><Input /></Form.Item>
      <Form.Item label="Kubeconfig 路径" name={["kubernetes", "kubeconfigPath"]}><Input /></Form.Item>
      <Form.Item label="StorageClass" name={["kubernetes", "storageClass"]}><Input /></Form.Item>
    </div>
  );
}

function MiddlewareSettingsForm() {
  return <div className={styles.middlewareGrid}>{MIDDLEWARE.map((key) => <MiddlewareItem key={key} name={key} />)}</div>;
}

function MiddlewareItem({ name }: { name: string }) {
  return (
    <section className={styles.middlewareItem}>
      <div className={styles.middlewareTitle}><strong>{name}</strong><Form.Item name={["middleware", name, "enabled"]} valuePropName="checked"><Switch size="small" /></Form.Item></div>
      <Form.Item label="Host" name={["middleware", name, "host"]}><Input /></Form.Item>
      <Form.Item label="Port" name={["middleware", name, "port"]}><InputNumber min={1} max={65535} className={styles.fullControl} /></Form.Item>
      <Form.Item label="账号" name={["middleware", name, "username"]}><Input /></Form.Item>
      <Form.Item label="密码" name={["middleware", name, "password"]}><Input.Password /></Form.Item>
      <Form.Item label="库 / Topic / Namespace" name={["middleware", name, "database"]}><Input /></Form.Item>
    </section>
  );
}
