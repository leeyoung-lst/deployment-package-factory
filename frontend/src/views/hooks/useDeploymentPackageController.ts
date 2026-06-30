import { useCallback, useEffect, useRef, useState } from "react";
import type { FormInstance } from "antd";
import type { CheckboxChangeEvent } from "antd/es/checkbox";
import {
  createDeploymentPackage,
  disableBusinessPlatform,
  getDeploymentPackageOptions,
  registerBusinessPlatform,
  type DeploymentServiceOption,
  type SourceEnv,
} from "../../api/deploymentPackages";
import { ApiError } from "../../api/client";
import { getSystemSettings } from "../../api/settings";
import { businessOptionsForEnv, businessOptionValue, businessPlatformRowKey, DEFAULT_IMAGE_MODE, DEFAULT_TARGET, EXPORT_WIZARD_STEPS, notReadyRegisteredMicroservices, serviceOptionsForEnv } from "../components/deploymentPackageUtils";
import type { useDeploymentPackageActions } from "./useDeploymentPackageActions";
import type { useDeploymentPackageState } from "./useDeploymentPackageState";
import { useMicroserviceDeliveryActions } from "./useMicroserviceDeliveryActions";

type DeploymentState = ReturnType<typeof useDeploymentPackageState>;
type DeploymentActions = ReturnType<typeof useDeploymentPackageActions>;

export function useDeploymentPackageController(form: FormInstance, registerForm: FormInstance, deploymentState: DeploymentState, actions: DeploymentActions, notify: NotifyHandlers) {
  const [loadingOptions, setLoadingOptions] = useState(false);
  const [building, setBuilding] = useState(false);
  const [registeringBusiness, setRegisteringBusiness] = useState(false);
  const [registerModalOpen, setRegisterModalOpen] = useState(false);
  const [exportWizardOpen, setExportWizardOpen] = useState(false);
  const [exportStep, setExportStep] = useState(0);
  const [disablingBusinessKey, setDisablingBusinessKey] = useState("");
  const [blockedMicroserviceKeys, setBlockedMicroserviceKeys] = useState<string[]>([]);
  const stateRef = useRef(deploymentState);
  const actionsRef = useRef(actions);
  const microserviceActions = useMicroserviceDeliveryActions(stateRef, actionsRef, notify);

  useEffect(() => { stateRef.current = deploymentState; actionsRef.current = actions; }, [actions, deploymentState]);

  const loadOptions = useCallback(async () => {
    setLoadingOptions(true);
    try {
      const [payload, settings] = await Promise.all([getDeploymentPackageOptions(), getSystemSettings()]);
      const state = stateRef.current;
      state.setOptions(payload); state.setSystemSettings(settings);
      const sourceEnv = payload.sourceEnvs.includes(state.sourceEnv) ? state.sourceEnv : (payload.sourceEnvs[0] ?? "test");
      state.setSourceEnv(sourceEnv);
      state.setPlatformServices((current) => Array.from(new Set([...serviceOptionsForEnv(payload.platformServices, sourceEnv).filter((item) => item.required).map((item) => item.key), ...current])));
      state.setBusinessServices((current) => current.filter((value) => businessOptionsForEnv(payload.businessServices, sourceEnv).some((item) => businessOptionValue(item) === value)));
      const databases = serviceOptionsForEnv(payload.databaseOptions, sourceEnv);
      state.setDatabase(databases.some((item) => item.key === "postgres") ? "postgres" : (databases[0]?.key ?? ""));
      if (payload.projects[0]) state.applyProjectDefaults(payload.projects[0].key, payload, settings);
      else { state.setProjectKey(""); state.setProductVersion(""); }
    } catch (error) {
      notify.error(error instanceof Error ? error.message : "部署包选项加载失败");
    } finally {
      setLoadingOptions(false);
    }
  }, [notify]);

  const openExportWizard = useCallback(() => {
    form.setFieldsValue({ ...DEFAULT_TARGET, ...stateRef.current.targetDraft, imageMode: stateRef.current.targetDraft.imageMode ?? DEFAULT_IMAGE_MODE });
    setExportStep(0); setExportWizardOpen(true);
  }, [form]);

  const openBlockedMicroservices = useCallback((serviceKeys: string[]) => {
    form.setFieldsValue({ ...DEFAULT_TARGET, ...stateRef.current.targetDraft, imageMode: stateRef.current.targetDraft.imageMode ?? DEFAULT_IMAGE_MODE });
    setBlockedMicroserviceKeys(serviceKeys);
    setExportStep(EXPORT_WIZARD_STEPS.length - 1);
    setExportWizardOpen(true);
  }, [form]);

  const validateExportStep = useCallback(async (step = exportStep) => {
    const state = stateRef.current;
    if (step === 0 && !state.projectKey && state.options?.projects.length) { notify.warning("请选择项目"); return false; }
    if (step === 0 && !state.productVersion && (state.selectedProject?.versions.length ?? 0) > 0) { notify.warning("请选择产品版本"); return false; }
    if (step === 0 && (!state.sourceEnv || !state.deployMode)) { notify.warning("请选择来源环境和部署方式"); return false; }
    if (step === 2 && !state.database) { notify.warning("请选择数据库中间件"); return false; }
    if (step === 3) await form.validateFields(["env", "namespacePrefix", "domain"]);
    return true;
  }, [exportStep, form, notify]);

  const goNextExportStep = useCallback(async () => {
    try { if (await validateExportStep()) setExportStep((current) => Math.min(current + 1, EXPORT_WIZARD_STEPS.length - 1)); }
    catch (error) { if (error instanceof Error) notify.error(error.message); }
  }, [notify, validateExportStep]);

  const openRegisterModal = useCallback(() => {
    registerForm.setFieldsValue({ sourceEnv: stateRef.current.sourceEnv, key: "", name: "", profile: "" });
    setRegisterModalOpen(true);
  }, [registerForm]);

  const submitBusinessRegistration = useCallback(async () => {
    try {
      const values = await registerForm.validateFields();
      setRegisteringBusiness(true);
      await registerBusinessPlatform({ sourceEnv: values.sourceEnv, key: values.key, name: values.name, profile: values.profile || "" });
      notify.success("业务平台 namespace 已注册"); setRegisterModalOpen(false); await loadOptions(); void actionsRef.current.refreshAuditEvents();
    } catch (error) { if (error instanceof Error) notify.error(error.message); }
    finally { setRegisteringBusiness(false); }
  }, [loadOptions, notify, registerForm]);

  const disableBusiness = useCallback(async (item: DeploymentServiceOption) => {
    if (!item.sourceEnv || !item.key) return;
    setDisablingBusinessKey(businessPlatformRowKey(item));
    try { await disableBusinessPlatform(item.sourceEnv as SourceEnv, item.key, item.profile || ""); notify.success("业务平台已注销"); await loadOptions(); void actionsRef.current.refreshAuditEvents(); }
    catch (error) { notify.error(error instanceof Error ? error.message : "业务平台注销失败"); }
    finally { setDisablingBusinessKey(""); }
  }, [loadOptions, notify]);

  const buildPackage = useCallback(async () => {
    try {
      if (!(await validateExportStep(0)) || !(await validateExportStep(2)) || !(await validateExportStep(3))) return;
      const values = await form.validateFields();
      const state = stateRef.current;
      const notReady = notReadyRegisteredMicroservices(state.businessServices, state.businessOptionsForSourceEnv, state.options?.microservices ?? []);
      if (notReady.length) { notify.warning(`以下微服务尚未构建成功：${notReady.map((item) => item.serviceName || item.serviceKey).join("、")}`); return; }
      setBuilding(true);
      setBlockedMicroserviceKeys([]);
      const payload = await createDeploymentPackage({ ...state.makePreviewPayload(), imageMode: values.imageMode, targetProfile: { env: values.env, domain: values.domain, sourceRegistry: values.sourceRegistry || "", sourceRegistryInsecure: Boolean(values.sourceRegistryInsecure), registry: values.registry || "", namespacePrefix: values.namespacePrefix, storageClass: values.storageClass || "", exportImages: values.imageMode === "image-archive" } });
      actionsRef.current.setTask(payload); void actionsRef.current.refreshTasks(); void actionsRef.current.refreshAuditEvents();
      notify.success("部署任务已创建"); setExportWizardOpen(false); setExportStep(0);
    } catch (error) {
      if (isMicroserviceDeliveryBlocked(error)) {
        setBlockedMicroserviceKeys(blockedServiceKeys(error.detail));
        setExportStep(EXPORT_WIZARD_STEPS.length - 1);
        notify.warning(`${error.message}，请刷新状态或重试交付`);
      } else if (error instanceof Error) notify.error(error.message);
    }
    finally { setBuilding(false); }
  }, [form, notify, validateExportStep]);

  const onRequiredPlatformClick = (event: CheckboxChangeEvent) => {
    if (!event.target.checked) notify.info("必选基础能力会自动保留在部署包中");
  };

  const onPlatformChange = (checkedValues: Array<string | number | boolean>) => {
    const selected = checkedValues.map(String);
    stateRef.current.setPlatformServices(Array.from(new Set([...stateRef.current.requiredPlatformKeys, ...selected])));
  };

  const onBusinessChange = (checkedValues: Array<string | number | boolean>) => {
    stateRef.current.setBusinessServices(checkedValues.map(String));
  };

  return { blockedMicroserviceKeys, buildPackage, building, disableBusiness, disablingBusinessKey, exportStep, exportWizardOpen, goNextExportStep, goPreviousExportStep: () => setExportStep((current) => Math.max(current - 1, 0)), loadOptions, loadingOptions, onBusinessChange, onPlatformChange, onRequiredPlatformClick, openBlockedMicroservices, openExportWizard, openRegisterModal, ...microserviceActions, registerModalOpen, registeringBusiness, setExportWizardOpen, setRegisterModalOpen, submitBusinessRegistration };
}

function isMicroserviceDeliveryBlocked(error: unknown): error is ApiError {
  return error instanceof ApiError && error.code === "MICROSERVICE_DELIVERY_NOT_READY";
}

function blockedServiceKeys(detail: unknown) {
  if (!detail || typeof detail !== "object" || !("services" in detail)) return [];
  const services = (detail as { services?: unknown }).services;
  if (!Array.isArray(services)) return [];
  return services.map((item) => typeof item === "object" && item && "serviceKey" in item ? String((item as { serviceKey?: unknown }).serviceKey || "") : "").filter(Boolean);
}

interface NotifyHandlers {
  error: (text: string) => void;
  info: (text: string) => void;
  success: (text: string) => void;
  warning: (text: string) => void;
}
