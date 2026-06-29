import { useCallback, useMemo, useState } from "react";
import type { FormInstance } from "antd";
import type { BusinessSelection, DeployMode, DeploymentPackageOptions, DeploymentServiceOption, PackagePreviewRequest, SourceEnv } from "../../api/deploymentPackages";
import type { SystemSettings } from "../../api/settings";
import { businessOptionsForEnv, businessOptionValue, DEFAULT_IMAGE_MODE, DEFAULT_TARGET, parseBusinessOptionValue, serviceOptionsForEnv, type TargetDraft } from "../components/deploymentPackageUtils";

export function useDeploymentPackageState(form: FormInstance) {
  const [options, setOptions] = useState<DeploymentPackageOptions | null>(null);
  const [projectKey, setProjectKey] = useState("");
  const [productVersion, setProductVersion] = useState("");
  const [sourceEnv, setSourceEnv] = useState<SourceEnv>("test");
  const [deployMode, setDeployMode] = useState<DeployMode>("k8s");
  const [platformServices, setPlatformServices] = useState<string[]>([]);
  const [businessServices, setBusinessServices] = useState<string[]>([]);
  const [database, setDatabase] = useState("");
  const [targetDraft, setTargetDraft] = useState<TargetDraft>({ ...DEFAULT_TARGET, imageMode: DEFAULT_IMAGE_MODE });
  const [systemSettings, setSystemSettings] = useState<SystemSettings | null>(null);

  const requiredPlatformKeys = useMemo(() => options?.platformServices.filter((item) => item.required).map((item) => item.key) ?? [], [options]);
  const selectedProject = useMemo(() => options?.projects.find((item) => item.key === projectKey) ?? null, [options?.projects, projectKey]);
  const businessOptionsForSourceEnv = useMemo(() => businessOptionsForEnv(options?.businessServices ?? [], sourceEnv), [options?.businessServices, sourceEnv]);
  const platformOptionsForSourceEnv = useMemo(() => serviceOptionsForEnv(options?.platformServices ?? [], sourceEnv), [options?.platformServices, sourceEnv]);
  const databaseOptionsForSourceEnv = useMemo(() => serviceOptionsForEnv(options?.databaseOptions ?? [], sourceEnv), [options?.databaseOptions, sourceEnv]);
  const registeredBusinessOptions = useMemo(() => (options?.businessServices ?? []).filter((item) => item.registered && item.status !== "disabled"), [options?.businessServices]);
  const selectedPlatformOptions = useMemo(() => platformOptionsForSourceEnv.filter((item) => platformServices.includes(item.key)), [platformOptionsForSourceEnv, platformServices]);
  const selectedBusinessOptions = useMemo(() => businessServices.map((value) => options?.businessServices.find((item) => businessOptionValue(item) === value)).filter((item): item is DeploymentServiceOption => Boolean(item)), [businessServices, options?.businessServices]);
  const selectedDatabaseOption = useMemo(() => databaseOptionsForSourceEnv.find((item) => item.key === database) ?? null, [database, databaseOptionsForSourceEnv]);

  const defaultTargetRegistry = useCallback((project?: { registry?: string } | null, settingsOverride?: SystemSettings | null) => project?.registry || settingsOverride?.harbor.registry || systemSettings?.harbor.registry || "", [systemSettings?.harbor.registry]);

  const applyProjectDefaults = useCallback((key: string, sourceOptions = options, settingsOverride?: SystemSettings | null) => {
    const project = sourceOptions?.projects.find((item) => item.key === key);
    setProjectKey(key);
    if (!project) return;
    const projectSourceEnv = project.defaultSourceEnv;
    setProductVersion(project.defaultVersion || project.versions[0] || "");
    setSourceEnv(projectSourceEnv);
    setDeployMode(project.defaultDeployModes[0] || "k8s");
    setPlatformServices(project.defaultPlatformServices.filter((item) => serviceOptionsForEnv(sourceOptions?.platformServices ?? [], projectSourceEnv).some((option) => option.key === item)));
    setBusinessServices(project.defaultBusinessServices.map((item) => businessOptionValue({ key: item.name, profile: item.profile })).filter((value) => businessOptionsForEnv(sourceOptions?.businessServices ?? [], projectSourceEnv).some((item) => businessOptionValue(item) === value)));
    const projectDatabases = serviceOptionsForEnv(sourceOptions?.databaseOptions ?? [], projectSourceEnv);
    setDatabase(projectDatabases.some((item) => item.key === project.defaultDatabase) ? project.defaultDatabase : (projectDatabases[0]?.key ?? ""));
    const nextTarget = { domain: project.domain, registry: defaultTargetRegistry(project, settingsOverride), namespacePrefix: project.namespacePrefix, storageClass: project.storageClass };
    form.setFieldsValue(nextTarget);
    setTargetDraft((current) => ({ ...current, ...nextTarget }));
  }, [defaultTargetRegistry, form, options]);

  const makePreviewPayload = useCallback((): PackagePreviewRequest => {
    const selectedBusiness: BusinessSelection[] = businessServices.map((value) => {
      const item = options?.businessServices.find((candidate) => businessOptionValue(candidate) === value);
      const fallback = parseBusinessOptionValue(value);
      return { name: item?.key || fallback.key, profile: item?.profile || fallback.profile };
    });
    const { imageMode, ...previewTargetProfile } = targetDraft;
    return { projectKey, productVersion, sourceEnv, deployModes: [deployMode], platformServices, businessServices: selectedBusiness, database, targetProfile: { ...previewTargetProfile, exportImages: imageMode === "image-archive" } };
  }, [businessServices, database, deployMode, options?.businessServices, platformServices, productVersion, projectKey, sourceEnv, targetDraft]);

  return { applyProjectDefaults, businessOptionsForSourceEnv, businessServices, database, databaseOptionsForSourceEnv, deployMode, makePreviewPayload, options, platformOptionsForSourceEnv, platformServices, productVersion, projectKey, registeredBusinessOptions, requiredPlatformKeys, selectedBusinessOptions, selectedDatabaseOption, selectedPlatformOptions, selectedProject, setBusinessServices, setDatabase, setDeployMode, setOptions, setPlatformServices, setProductVersion, setProjectKey, setSourceEnv, setSystemSettings, setTargetDraft, sourceEnv, targetDraft };
}
