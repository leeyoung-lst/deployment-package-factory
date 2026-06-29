import { buildDownloadUrl, request } from "./client";
import type { SourceEnv } from "./deploymentPackages";

export interface MicroserviceScaffoldOptions {
  projectKinds: Array<{ key: string; name: string }>;
  techStacks: Array<{ key: string; name: string }>;
  middleware: Array<{ key: string; name: string }>;
}

export interface MicroserviceScaffoldRequest {
  serviceKey: string;
  serviceName: string;
  description: string;
  projectKind: string;
  techStack: string;
  port: number;
  middleware: string[];
  sourceEnv: SourceEnv;
  businessPlatformKey: string;
  businessPlatformProfile: string;
  gitGroup: string;
  imageRegistry: string;
  imageNamespace: string;
  k8sNamespace: string;
}

export interface MicroserviceScaffoldResult {
  projectId: string;
  serviceKey: string;
  serviceName: string;
  techStack: string;
  sourceEnv: SourceEnv;
  businessPlatformKey: string;
  businessPlatformProfile: string;
  businessPlatformName: string;
  businessPlatformNamespace: string;
  artifactName: string;
  artifactPath: string;
  artifactSize: number;
  sha256: string;
  downloadUrl: string;
  downloadCommand: string;
  cloneCommand: string;
  generatedFiles: string[];
  validation: {
    passed: boolean;
    fileCount: number;
    checks: Array<{ name: string; passed: boolean; message: string }>;
  };
}

export interface RegisteredMicroservice {
  projectId: string;
  serviceKey: string;
  serviceName: string;
  description: string;
  projectKind: string;
  techStack: string;
  port: number;
  middleware: string[];
  sourceEnv: SourceEnv;
  businessPlatformKey: string;
  businessPlatformProfile: string;
  businessPlatformName: string;
  businessPlatformNamespace: string;
  gitGroup: string;
  imageRegistry: string;
  imageNamespace: string;
  image: string;
  k8sNamespace: string;
  artifactName: string;
  artifactPath: string;
  sha256: string;
  generatedFiles: string[];
  status: string;
  createdAt: string;
  updatedAt: string;
}

export function getMicroserviceScaffoldOptions() {
  return request<MicroserviceScaffoldOptions>("/api/microservices/options");
}

export function registerMicroservice(payload: MicroserviceScaffoldRequest) {
  return request<MicroserviceScaffoldResult>("/api/microservices", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listMicroservices(params?: {
  sourceEnv?: SourceEnv;
  businessPlatformKey?: string;
  businessPlatformProfile?: string;
}) {
  const search = new URLSearchParams();
  if (params?.sourceEnv) search.set("source_env", params.sourceEnv);
  if (params?.businessPlatformKey) search.set("business_platform_key", params.businessPlatformKey);
  if (params?.businessPlatformProfile) search.set("business_platform_profile", params.businessPlatformProfile);
  const query = search.toString();
  return request<RegisteredMicroservice[]>(`/api/microservices${query ? `?${query}` : ""}`);
}

export function downloadMicroserviceScaffold(projectId: string) {
  return buildDownloadUrl(`/api/microservices/${encodeURIComponent(projectId)}/download`);
}
