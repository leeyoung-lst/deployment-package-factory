import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { App } from "antd";
import {
  DEFAULT_RESET_OPTIONS,
  executeEnvironmentReset,
  previewEnvironmentReset,
  type EnvironmentResetOptions,
  type EnvironmentResetPreview,
} from "../../api/environmentReset";

export function useEnvironmentReset() {
  const { message } = App.useApp();
  const [options, setOptions] = useState<EnvironmentResetOptions>(DEFAULT_RESET_OPTIONS);
  const [preview, setPreview] = useState<EnvironmentResetPreview | null>(null);
  const [loading, setLoading] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmation, setConfirmation] = useState("");
  const initialized = useRef(false);

  const confirmationPhrase = preview?.confirmationPhrase || "RESET deployment-package-factory";
  const canExecute = confirmation === confirmationPhrase;
  const selectedKeys = useMemo(
    () => Object.entries(options).filter(([, selected]) => selected).map(([key]) => key),
    [options],
  );

  const updateOption = (key: keyof EnvironmentResetOptions, checked: boolean) => {
    setOptions((current) => ({ ...current, [key]: checked }));
  };

  const runPreview = useCallback(async () => {
    setLoading(true);
    try {
      const payload = await previewEnvironmentReset(options);
      setPreview(payload);
      message.success("清理预览已刷新");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "清理预览失败");
    } finally {
      setLoading(false);
    }
  }, [message, options]);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    void runPreview();
  }, [runPreview]);

  const executeReset = async () => {
    setExecuting(true);
    try {
      const payload = await executeEnvironmentReset(options, confirmation);
      setPreview(payload);
      setConfirmOpen(false);
      setConfirmation("");
      message.success("环境数据已清理");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "环境清理失败");
    } finally {
      setExecuting(false);
    }
  };

  return {
    canExecute,
    confirmation,
    confirmationPhrase,
    confirmOpen,
    executeReset,
    executing,
    loading,
    options,
    preview,
    runPreview,
    selectedKeys,
    setConfirmation,
    setConfirmOpen,
    updateOption,
  };
}
