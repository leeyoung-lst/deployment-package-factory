import { useEffect, useMemo, useState } from "react";
import type { FormInstance } from "antd";
import { getDeploymentPackageOptions, type DeploymentPackageOptions, type SourceEnv } from "../../api/deploymentPackages";
import { getSystemSettings, type SystemSettings } from "../../api/settings";
import { getMicroserviceScaffoldOptions, listMicroservices, registerMicroservice, type MicroserviceScaffoldOptions, type MicroserviceScaffoldResult, type RegisteredMicroservice } from "../../api/microservices";
import { businessPlatformValue, normalizeK8sName, normalizePathValue, normalizeRegistry, parseApiErrorDetails, parseBusinessPlatformValue } from "../components/microserviceUtils";

export const DEFAULT_MICROSERVICE_VALUES = {
  serviceKey: "asset-service",
  serviceName: "资产服务",
  description: "",
  projectKind: "backend",
  techStack: "python-fastapi",
  port: 8000,
  middleware: ["redis", "postgresql"],
  sourceEnv: "test" as SourceEnv,
  businessPlatform: "",
  gitGroup: "",
  imageRegistry: "",
  imageNamespace: "",
  k8sNamespace: "",
};

export type MicroserviceWizardValues = typeof DEFAULT_MICROSERVICE_VALUES;

const API_FIELD_STEPS: Record<string, number> = { sourceEnv: 0, businessPlatformKey: 0, serviceKey: 1, serviceName: 1, projectKind: 1, techStack: 1, port: 2, middleware: 2, gitGroup: 2, imageRegistry: 2, imageNamespace: 2, k8sNamespace: 2 };

export function useMicroserviceRegistration(form: FormInstance<MicroserviceWizardValues>, notifyError: (message: string) => void) {
  const [options, setOptions] = useState<MicroserviceScaffoldOptions | null>(null);
  const [deploymentOptions, setDeploymentOptions] = useState<DeploymentPackageOptions | null>(null);
  const [systemSettings, setSystemSettings] = useState<SystemSettings | null>(null);
  const [registeredServices, setRegisteredServices] = useState<RegisteredMicroservice[]>([]);
  const [result, setResult] = useState<MicroserviceScaffoldResult | null>(null);
  const [formValues, setFormValues] = useState<MicroserviceWizardValues>(DEFAULT_MICROSERVICE_VALUES);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);

  const sourceEnv = formValues.sourceEnv;
  const businessPlatforms = useMemo(() => (deploymentOptions?.businessServices ?? []).filter((item) => item.registered && item.status !== "disabled" && item.sourceEnv === sourceEnv), [deploymentOptions?.businessServices, sourceEnv]);
  const selectedPlatform = useMemo(() => businessPlatforms.find((item) => businessPlatformValue(item) === formValues.businessPlatform), [businessPlatforms, formValues.businessPlatform]);

  const loadOptions = async () => {
    setLoading(true);
    try {
      const [scaffoldOptions, packageOptions, services, settings] = await Promise.all([getMicroserviceScaffoldOptions(), getDeploymentPackageOptions(), listMicroservices(), getSystemSettings()]);
      const firstPlatform = packageOptions.businessServices.find((item) => item.registered && item.status !== "disabled");
      const values = { ...DEFAULT_MICROSERVICE_VALUES, sourceEnv: firstPlatform?.sourceEnv || packageOptions.sourceEnvs[0] || "test", businessPlatform: firstPlatform ? businessPlatformValue(firstPlatform) : "", gitGroup: settings.git.group, imageRegistry: settings.harbor.registry, imageNamespace: settings.harbor.project };
      setOptions(scaffoldOptions); setDeploymentOptions(packageOptions); setRegisteredServices(services); setSystemSettings(settings); setFormValues(values); form.setFieldsValue(values);
    } catch (error) {
      notifyError(error instanceof Error ? error.message : "微服务注册选项加载失败");
    } finally {
      setLoading(false);
    }
  };

  const normalizeCurrentInputs = () => {
    form.setFieldsValue({ serviceKey: normalizeK8sName(form.getFieldValue("serviceKey")), gitGroup: normalizePathValue(form.getFieldValue("gitGroup")), imageRegistry: normalizeRegistry(form.getFieldValue("imageRegistry")), imageNamespace: normalizePathValue(form.getFieldValue("imageNamespace")), k8sNamespace: normalizeK8sName(form.getFieldValue("k8sNamespace")) });
    setFormValues(form.getFieldsValue(true));
  };

  const submit = async () => {
    try {
      normalizeCurrentInputs();
      await form.validateFields();
      const values = form.getFieldsValue(true);
      const platform = parseBusinessPlatformValue(values.businessPlatform);
      setSubmitting(true);
      const payload = await registerMicroservice({ ...values, businessPlatformKey: platform.key, businessPlatformProfile: platform.profile });
      setResult(payload); setFormValues(values); setRegisteredServices(await listMicroservices()); setWizardOpen(false);
      return true;
    } catch (error) {
      focusApiErrorStep(error);
      if (error instanceof Error) notifyError(error.message);
      return false;
    } finally {
      setSubmitting(false);
    }
  };

  const focusApiErrorStep = (error: unknown) => {
    const field = parseApiErrorDetails(error).map((item) => item.loc.at(-1)).find((item): item is string => Boolean(item && API_FIELD_STEPS[item] !== undefined));
    if (field) { setCurrentStep(API_FIELD_STEPS[field]); setWizardOpen(true); }
  };

  useEffect(() => { void loadOptions(); }, []);

  return { businessPlatforms, currentStep, deploymentOptions, formValues, loading, options, registeredServices, result, selectedPlatform, submitting, systemSettings, wizardOpen, loadOptions, normalizeCurrentInputs, setCurrentStep, setFormValues, setRegisteredServices, setWizardOpen, submit };
}
