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

  const loadSettings = async () => {
    setLoading(true);
    try {
      const payload = await getSystemSettings();
      form.setFieldsValue(payload);
      setUpdatedAt(payload.updatedAt || "");
    } catch (error) {
      notifyError(error instanceof Error ? error.message : "系统设置加载失败");
    } finally {
      setLoading(false);
    }
  };

  const saveSettings = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      const payload = await updateSystemSettings(values);
      form.setFieldsValue(payload);
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
