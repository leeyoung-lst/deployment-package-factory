import { useEffect, useState } from "react";
import type { FormInstance } from "antd";
import { importEnvironmentSettings, getSystemSettings, updateSystemSettings, type SystemSettings } from "../../api/settings";

export type SettingsSection = "git" | "harbor" | "jenkins" | "kubernetes" | "middleware";

export function useSystemSettings(form: FormInstance<SystemSettings>, notifyError: (message: string) => void) {
  const [activeSection, setActiveSection] = useState<SettingsSection>("git");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [importing, setImporting] = useState(false);
  const [updatedAt, setUpdatedAt] = useState("");
  const [importedFields, setImportedFields] = useState<string[]>([]);
  const [settingsSnapshot, setSettingsSnapshot] = useState<SystemSettings | null>(null);

  const loadSettings = async () => {
    setLoading(true);
    try {
      const payload = await getSystemSettings();
      form.setFieldsValue(payload);
      setSettingsSnapshot(payload);
      setUpdatedAt(payload.updatedAt || "");
    } catch (error) {
      notifyError(error instanceof Error ? error.message : "系统设置加载失败");
    } finally {
      setLoading(false);
    }
  };

  const saveSettings = async () => {
    try {
      await form.validateFields();
      const values = mergeSystemSettings(settingsSnapshot, form.getFieldsValue(true));
      setSaving(true);
      const payload = await updateSystemSettings(values);
      form.setFieldsValue(payload);
      setSettingsSnapshot(payload);
      setUpdatedAt(payload.updatedAt || "");
      return true;
    } catch (error) {
      if (error instanceof Error) notifyError(error.message);
      return false;
    } finally {
      setSaving(false);
    }
  };

  const importWorkbook = async (file: File) => {
    setImporting(true);
    try {
      const result = await importEnvironmentSettings(file);
      form.setFieldsValue(result.settings);
      setSettingsSnapshot(result.settings);
      setUpdatedAt(result.settings.updatedAt || "");
      setImportedFields(result.importedFields);
      return result;
    } catch (error) {
      notifyError(error instanceof Error ? error.message : "环境信息导入失败");
      return null;
    } finally {
      setImporting(false);
    }
  };

  useEffect(() => {
    void loadSettings();
  }, []);

  return {
    activeSection,
    importedFields,
    importing,
    loading,
    saving,
    updatedAt,
    importWorkbook,
    loadSettings,
    saveSettings,
    setActiveSection,
  };
}

function mergeSystemSettings(base: SystemSettings | null, values: Partial<SystemSettings>): SystemSettings {
  return {
    ...(base ?? ({} as SystemSettings)),
    ...values,
    git: { ...(base?.git ?? {}), ...(values.git ?? {}) },
    harbor: { ...(base?.harbor ?? {}), ...(values.harbor ?? {}) },
    jenkins: { ...(base?.jenkins ?? {}), ...(values.jenkins ?? {}) },
    kubernetes: { ...(base?.kubernetes ?? {}), ...(values.kubernetes ?? {}) },
    middleware: mergeMiddleware(base?.middleware, values.middleware),
    updatedAt: values.updatedAt ?? base?.updatedAt ?? "",
  } as SystemSettings;
}

function mergeMiddleware(base: SystemSettings["middleware"] | undefined, values: SystemSettings["middleware"] | undefined) {
  const merged = { ...(base ?? {}) };
  for (const [key, value] of Object.entries(values ?? {})) {
    merged[key] = { ...(merged[key] ?? {}), ...value };
  }
  return merged;
}
