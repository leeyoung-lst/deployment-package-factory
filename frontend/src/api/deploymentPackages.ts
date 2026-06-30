import { buildDownloadUrl, request } from "./client";

export type DeployMode = "k8s" | "docker-compose";
export type SourceEnv = "dev" | "test";

export interface DeploymentServiceOption {
  key: string;
  name: string;
  required?: boolean;
  profile?: string;
  namespaceGroup?: string;
  namespace?: string;
  sourceEnv?: SourceEnv | "";
  status?: string;
  registered?: boolean;
}

export interface DatabaseOption {
  key: string;
  name: string;
  domestic: boolean;
  image: string;
  sourceEnv?: SourceEnv | "";
}

export interface MiddlewareOption {
  key: string;
  name: string;
  image: string;
  sourceEnv?: SourceEnv | "";
}

export interface DeploymentPackageOptions {
  sourceEnvs: SourceEnv[];
  deployModes: DeployMode[];
  platformServices: DeploymentServiceOption[];
  businessServices: DeploymentServiceOption[];
  databaseOptions: DatabaseOption[];
  middleware: MiddlewareOption[];
  microservices: RegisteredDeploymentMicroservice[];
  projects: ProjectProfile[];
}

export interface RegisteredDeploymentMicroservice {
  projectId: string;
  serviceKey: string;
  serviceName: string;
  sourceEnv: SourceEnv;
  businessPlatformKey: string;
  businessPlatformProfile: string;
  businessPlatformNamespace: string;
  image: string;
  k8sNamespace: string;
  status: string;
  gitRepositoryUrl?: string;
  cloneCommand?: string;
  buildCommand?: string;
  deployCommand?: string;
  jenkinsJob?: string;
  delivery?: MicroserviceDelivery;
}

export interface MicroserviceDelivery {
  status?: string;
  steps?: MicroserviceDeliveryStep[];
  build?: MicroserviceBuildStatus;
}

export interface MicroserviceDeliveryStep {
  name: string;
  status: string;
  message?: string;
  target?: string;
  phase?: string;
  action?: string;
  retryable?: boolean;
  elapsedMs?: number;
  hint?: string;
}

export interface MicroserviceBuildStatus {
  status?: string;
  result?: string | null;
  building?: boolean;
  url?: string;
  number?: number | null;
  message?: string;
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
  targetProfile?: Partial<TargetProfile>;
  runtimeConfigOverrides?: Record<string, string>;
}

export interface PackageBuildRequest extends PackagePreviewRequest {
  imageMode: "image-manifest" | "image-archive";
  targetProfile: TargetProfile;
  runtimeConfigOverrides: Record<string, string>;
}

export interface RuntimeConfigItem {
  name: string;
  envName: string;
  overrideName: string;
  label: string;
  value: string;
  sensitive: boolean;
  source: string;
  resolved: boolean;
}

export interface RuntimeConfigGroup {
  key: string;
  name: string;
  items: RuntimeConfigItem[];
}

export interface RuntimeResource {
  key: string;
  type: "databaseSchema" | "bucket" | "collection" | string;
  name: string;
  middlewareKey: string;
  source: string;
  needsReview: boolean;
  shared: boolean;
  usedBy: string[];
  items: RuntimeConfigItem[];
}

export interface RuntimeConfigPreview {
  groups: RuntimeConfigGroup[];
  resources: RuntimeResource[];
}

export interface TargetProfile {
  env: string;
  domain: string;
  sourceRegistry: string;
  sourceRegistryInsecure: boolean;
  registry: string;
  namespacePrefix: string;
  storageClass: string;
  exportImages: boolean;
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
  namespace?: string;
  sourceEnv?: SourceEnv | "";
  status?: string;
}

export interface PackagePreview {
  platformServices: ResolvedDependency[];
  businessServices: ResolvedDependency[];
  middleware: ResolvedDependency[];
  database: DatabaseOption;
  images: Record<string, string[]>;
  imageEntries: ImageEntry[];
  runtimeConfig: RuntimeConfigPreview;
  warnings: string[];
}

export interface ImageEntry {
  group: string;
  catalogRef: string;
  sourceRef: string;
  sourceExportRef?: string;
  targetRef: string;
  sourceResolvedFrom?: string;
  sourceMissing?: boolean;
  sourceMessage?: string;
  sourceImageId?: string;
  sourceNamespace?: string;
  sourcePod?: string;
  sourceContainer?: string;
  archiveFile?: string;
}

export interface BusinessPlatformRegistrationRequest {
  sourceEnv: SourceEnv;
  key: string;
  name: string;
  profile?: string;
}

export interface BusinessPlatformRegistrationResult {
  key: string;
  name: string;
  profile: string;
  namespace: string;
  sourceEnv: SourceEnv;
  status: string;
}

export interface PackageBuildResult {
  packageId: string;
  workDir: string;
  artifactPath: string;
  checksumPath: string;
  artifactSize: number;
  validationSummary: {
    artifactSize?: number;
    packageIndexFileCount?: number;
    packageIndexTotalBytes?: number;
    imageEntryCount?: number;
    imageArchiveCount?: number;
    missingImageArchiveCount?: number;
  };
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
  artifactAvailable: boolean;
  error: string;
  logs: string[];
  workerId: string;
  claimedAt: string;
  heartbeatAt: string;
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

export interface ImageExportEnvironmentCheck {
  available: boolean;
  exportTool: string;
  toolVersion: string;
  dockerVersion: string;
  message: string;
}

export interface AuditEvent {
  eventId: string;
  action: string;
  targetId: string;
  status: string;
  operator: string;
  clientIp: string;
  message: string;
  metadata: Record<string, unknown>;
  createdAt: string;
}

export interface AuditEventQuery {
  limit?: number;
  status?: string;
  action?: string;
  actionPrefix?: string;
}

export function getDeploymentPackageOptions() {
  return request<DeploymentPackageOptions>("/api/deployment-packages/options");
}

export function getImageExportEnvironment() {
  return request<ImageExportEnvironmentCheck>("/api/deployment-packages/image-export-environment");
}

export function previewDeploymentPackage(payload: PackagePreviewRequest) {
  return request<PackagePreview>("/api/deployment-packages/preview", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function registerBusinessPlatform(payload: BusinessPlatformRegistrationRequest) {
  return request<BusinessPlatformRegistrationResult>("/api/deployment-packages/business-platforms/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function disableBusinessPlatform(sourceEnv: SourceEnv, businessKey: string, profile = "") {
  const query = profile ? `?profile=${encodeURIComponent(profile)}` : "";
  return request<BusinessPlatformRegistrationResult>(
    `/api/deployment-packages/business-platforms/${encodeURIComponent(sourceEnv)}/${encodeURIComponent(businessKey)}/disable${query}`,
    { method: "POST" },
  );
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

export function listDeploymentPackageAuditEvents(query: AuditEventQuery = { limit: 20 }) {
  const search = new URLSearchParams();
  search.set("limit", String(query.limit ?? 20));
  if (query.status) search.set("status", query.status);
  if (query.action) search.set("action", query.action);
  if (query.actionPrefix) search.set("actionPrefix", query.actionPrefix);
  return request<AuditEvent[]>(`/api/deployment-packages/audit-events?${search.toString()}`);
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

export function downloadDeploymentPackage(packageId: string) {
  return buildDownloadUrl(`/api/deployment-packages/${encodeURIComponent(packageId)}/download`);
}

export function downloadDeploymentPackageChecksum(packageId: string) {
  return buildDownloadUrl(`/api/deployment-packages/${encodeURIComponent(packageId)}/checksum`);
}

export function downloadDeploymentPackageScript(packageId: string, shell: "powershell" | "bash") {
  const suffix = shell === "powershell" ? "download-script.ps1" : "download-script.sh";
  return buildDownloadUrl(`/api/deployment-packages/${encodeURIComponent(packageId)}/${suffix}`);
}
