import { useCallback, useState, type MutableRefObject } from "react";
import { getMicroserviceDeliveryStatus, retryMicroserviceDelivery, type RegisteredMicroservice } from "../../api/microservices";
import { selectedRegisteredMicroservices } from "../components/deploymentPackageUtils";
import type { useDeploymentPackageActions } from "./useDeploymentPackageActions";
import type { useDeploymentPackageState } from "./useDeploymentPackageState";

type DeploymentState = ReturnType<typeof useDeploymentPackageState>;
type DeploymentActions = ReturnType<typeof useDeploymentPackageActions>;

export function useMicroserviceDeliveryActions(stateRef: MutableRefObject<DeploymentState>, actionsRef: MutableRefObject<DeploymentActions>, notify: NotifyHandlers) {
  const [refreshingMicroservices, setRefreshingMicroservices] = useState(false);
  const [retryingMicroserviceId, setRetryingMicroserviceId] = useState("");

  const refreshMicroserviceDeliveries = useCallback(async () => {
    const state = stateRef.current;
    const selected = selectedRegisteredMicroservices(state.businessServices, state.businessOptionsForSourceEnv, state.options?.microservices ?? []);
    if (!selected.length) { notify.info("当前业务平台暂无注册微服务"); return; }
    setRefreshingMicroservices(true);
    try {
      const refreshed = await Promise.all(selected.map((item) => getMicroserviceDeliveryStatus(item.projectId)));
      mergeMicroservices(state, refreshed.map((item) => item.microservice).filter((item): item is RegisteredMicroservice => Boolean(item)));
      notify.success("微服务构建状态已刷新");
      void actionsRef.current.refreshPreview(state.makePreviewPayload());
    } catch (error) { notify.error(error instanceof Error ? error.message : "微服务构建状态刷新失败"); }
    finally { setRefreshingMicroservices(false); }
  }, [actionsRef, notify, stateRef]);

  const retryMicroservice = useCallback(async (projectId: string) => {
    setRetryingMicroserviceId(projectId);
    try {
      const result = await retryMicroserviceDelivery(projectId);
      const state = stateRef.current;
      if (result.microservice) mergeMicroservices(state, [result.microservice]);
      notify.success("微服务交付已重试");
      void actionsRef.current.refreshPreview(state.makePreviewPayload());
    } catch (error) { notify.error(error instanceof Error ? error.message : "微服务交付重试失败"); }
    finally { setRetryingMicroserviceId(""); }
  }, [actionsRef, notify, stateRef]);

  return { refreshMicroserviceDeliveries, refreshingMicroservices, retryMicroservice, retryingMicroserviceId };
}

function mergeMicroservices(state: DeploymentState, services: RegisteredMicroservice[]) {
  state.setOptions((current) => {
    if (!current) return current;
    const byId = new Map(services.map((item) => [item.projectId, item]));
    return { ...current, microservices: current.microservices.map((item) => byId.get(item.projectId) ?? item) };
  });
}

interface NotifyHandlers {
  error: (text: string) => void;
  info: (text: string) => void;
  success: (text: string) => void;
}
