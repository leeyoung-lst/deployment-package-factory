import { request } from "./client";

export interface EnvironmentResetOptions {
  packageTasks: boolean;
  auditEvents: boolean;
  businessPlatforms: boolean;
  microservices: boolean;
  packageArtifacts: boolean;
  packageWorkDirs: boolean;
  systemSettings: boolean;
}

export interface ResetTableSummary {
  name: string;
  selected: boolean;
  existingRows: number;
  deletedRows: number;
}

export interface ResetPathSummary {
  name: string;
  path: string;
  selected: boolean;
  exists: boolean;
  files: number;
  directories: number;
  bytes: number;
  deletedFiles: number;
  deletedDirectories: number;
  freedBytes: number;
}

export interface EnvironmentResetPreview {
  namespace: string;
  confirmationPhrase: string;
  dryRun: boolean;
  tables: ResetTableSummary[];
  paths: ResetPathSummary[];
  totalRows: number;
  selectedRows: number;
  deletedRows: number;
  totalFiles: number;
  selectedFiles: number;
  deletedFiles: number;
  totalBytes: number;
  selectedBytes: number;
  freedBytes: number;
}

export const DEFAULT_RESET_OPTIONS: EnvironmentResetOptions = {
  packageTasks: true,
  auditEvents: true,
  businessPlatforms: true,
  microservices: true,
  packageArtifacts: true,
  packageWorkDirs: true,
  systemSettings: false,
};

export function previewEnvironmentReset(options: EnvironmentResetOptions) {
  return request<EnvironmentResetPreview>("/api/environment-reset/preview", {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function executeEnvironmentReset(options: EnvironmentResetOptions, confirmation: string) {
  return request<EnvironmentResetPreview>("/api/environment-reset/execute", {
    method: "POST",
    body: JSON.stringify({ options, confirmation }),
  });
}
