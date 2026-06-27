import { BASE, request } from "./client";

export type DeployMode = "k8s" | "docker-compose";
export type SourceEnv = "dev" | "test";

export interface DeploymentServiceOption {
  key: string;
  name: string;
  required?: boolean;
  profile?: string;
  namespaceGroup?: string;
}

export interface DatabaseOption {
  key: string;
  name: string;
  domestic: boolean;
  image: string;
}

export interface MiddlewareOption {
  key: string;
  name: string;
  image: string;
}

export interface DeploymentPackageOptions {
  sourceEnvs: SourceEnv[];
  deployModes: DeployMode[];
  platformServices: DeploymentServiceOption[];
  businessServices: DeploymentServiceOption[];
  databaseOptions: DatabaseOption[];
  middleware: MiddlewareOption[];
  projects: ProjectProfile[];
}

export interface BusinessSelection {
  name: string;
  profile?: string;
}

export interface PackagePreviewRequest {
  projectKey: string;
  productVersion: string;
  sourceEnv: SourceEnv;
  deployModes: DeployMode[];
  platformServices: string[];
  businessServices: BusinessSelection[];
  database: string;
}

export interface PackageBuildRequest extends PackagePreviewRequest {
  imageMode: "image-manifest" | "image-archive";
  targetProfile: {
    env: string;
    domain: string;
    registry: string;
    namespacePrefix: string;
    storageClass: string;
    exportImages: boolean;
  };
}

export interface ProjectProfile {
  key: string;
  name: string;
  description: string;
  defaultVersion: string;
  versions: string[];
  defaultSourceEnv: SourceEnv;
  defaultDeployModes: DeployMode[];
  defaultPlatformServices: string[];
  defaultBusinessServices: BusinessSelection[];
  defaultDatabase: string;
  registry: string;
  namespacePrefix: string;
  domain: string;
  storageClass: string;
  imageTag: string;
  overlays: string[];
}

export interface ResolvedDependency {
  key: string;
  name: string;
  locked: boolean;
  requiredBy: string[];
  reason: string;
}

export interface PackagePreview {
  platformServices: ResolvedDependency[];
  businessServices: ResolvedDependency[];
  middleware: ResolvedDependency[];
  database: DatabaseOption;
  images: Record<string, string[]>;
  warnings: string[];
}

export interface PackageBuildResult {
  packageId: string;
  workDir: string;
  artifactPath: string;
  sha256: string;
  manifest: Record<string, unknown>;
}

export type PackageTaskStatus = "pending" | "running" | "completed" | "failed" | "canceled";

export interface PackageTask {
  taskId: string;
  status: PackageTaskStatus;
  progress: number;
  message: string;
  request: Record<string, unknown>;
  result: PackageBuildResult | null;
  error: string;
  logs: string[];
  createdAt: string;
  updatedAt: string;
}

export interface CleanupResult {
  scannedTasks: number;
  deletedArtifacts: number;
  deletedWorkDirs: number;
  freedBytes: number;
  retainedBytes: number;
  dryRun: boolean;
  deletedPaths: string[];
}

export function getDeploymentPackageOptions() {
  return request<DeploymentPackageOptions>("/api/deployment-packages/options");
}

export function previewDeploymentPackage(payload: PackagePreviewRequest) {
  return request<PackagePreview>("/api/deployment-packages/preview", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createDeploymentPackage(payload: PackageBuildRequest) {
  return request<PackageTask>("/api/deployment-packages", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getDeploymentPackageTask(taskId: string) {
  return request<PackageTask>(`/api/deployment-packages/tasks/${encodeURIComponent(taskId)}`);
}

export function listDeploymentPackageTasks(limit = 20) {
  return request<PackageTask[]>(`/api/deployment-packages/tasks?limit=${encodeURIComponent(String(limit))}`);
}

export function cancelDeploymentPackageTask(taskId: string) {
  return request<PackageTask>(`/api/deployment-packages/tasks/${encodeURIComponent(taskId)}/cancel`, {
    method: "POST",
  });
}

export function retryDeploymentPackageTask(taskId: string) {
  return request<PackageTask>(`/api/deployment-packages/tasks/${encodeURIComponent(taskId)}/retry`, {
    method: "POST",
  });
}

export function cleanupDeploymentPackages(dryRun: boolean) {
  return request<CleanupResult>(`/api/deployment-packages/cleanup?dry_run=${dryRun ? "true" : "false"}`, {
    method: "POST",
  });
}

export function deploymentPackageDownloadUrl(packageId: string) {
  return `${BASE}/api/deployment-packages/${encodeURIComponent(packageId)}/download`;
}
