import React from "react";
import { Form, Radio, Select } from "antd";
import styles from "../../MicroserviceRegistrationView.module.css";
import type { MicroserviceWizardStepProps } from "./types";

export function TechStackStep({ form, options, onValuesChange }: MicroserviceWizardStepProps) {
  const projectKind = Form.useWatch("projectKind", form);
  const isFrontend = projectKind === "frontend";
  const techStacks = (options?.techStacks ?? []).filter((item) => !item.projectKind || item.projectKind === projectKind);
  const microFrontends = [{ key: "", name: "不启用" }, ...(options?.microFrontendFrameworks ?? [])];

  const selectProjectKind = (value: string) => {
    const first = (options?.techStacks ?? []).find((item) => item.projectKind === value);
    form.setFieldsValue({ techStack: first?.key || "", microFrontendFramework: "", mcpServerEnabled: false });
    onValuesChange(null, form.getFieldsValue(true));
  };

  return (
    <div className={styles.stepBody}>
      <Form.Item label="项目类型" name="projectKind" rules={[{ required: true }]}>
        <Radio.Group optionType="button" buttonStyle="solid" options={(options?.projectKinds ?? []).map((item) => ({ value: item.key, label: item.name }))} onChange={(event) => selectProjectKind(event.target.value)} />
      </Form.Item>
      <Form.Item label="技术栈" name="techStack" rules={[{ required: true }]}>
        <Select options={techStacks.map((item) => ({ value: item.key, label: item.name }))} />
      </Form.Item>
      {isFrontend ? (
        <Form.Item label="微前端框架" name="microFrontendFramework">
          <Radio.Group optionType="button" buttonStyle="solid" options={microFrontends.map((item) => ({ value: item.key, label: item.name }))} />
        </Form.Item>
      ) : null}
    </div>
  );
}
