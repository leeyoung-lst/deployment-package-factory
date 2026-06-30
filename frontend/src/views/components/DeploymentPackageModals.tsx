import React from "react";
import type { FormInstance } from "antd";
import type { ImageExportEnvironmentCheck, PackagePreview } from "../../api/deploymentPackages";
import { BusinessPlatformRegistrationModal } from "./BusinessPlatformRegistrationModal";
import { DeploymentPackageWizardModal } from "./DeploymentPackageWizardModal";
import { notReadyRegisteredMicroservices } from "./deploymentPackageUtils";
import type { useDeploymentPackageController } from "../hooks/useDeploymentPackageController";
import type { useDeploymentPackageState } from "../hooks/useDeploymentPackageState";
import type { DeploymentPackageOptions } from "../../api/deploymentPackages";

interface Props {
  controller: ReturnType<typeof useDeploymentPackageController>;
  deploymentState: ReturnType<typeof useDeploymentPackageState>;
  form: FormInstance;
  imageEnvironment: ImageExportEnvironmentCheck | null;
  imageEnvironmentLoading: boolean;
  options: DeploymentPackageOptions | null;
  preview: PackagePreview | null;
  previewing: boolean;
  registerForm: FormInstance;
  onRefreshPreview: () => void;
}

export function DeploymentPackageModals(props: Props) {
  const state = props.deploymentState;
  const controller = props.controller;
  const notReadyMicroservices = notReadyRegisteredMicroservices(state.businessServices, state.businessOptionsForSourceEnv, props.options?.microservices ?? []);
  return (
    <>
      <DeploymentPackageWizardModal
        businessOptionsForSourceEnv={state.businessOptionsForSourceEnv}
        businessServices={state.businessServices}
        building={controller.building}
        buildDisabled={notReadyMicroservices.length > 0 || controller.refreshingMicroservices}
        database={state.database}
        databaseOptionsForSourceEnv={state.databaseOptionsForSourceEnv}
        deployMode={state.deployMode}
        form={props.form}
        imageEnvironment={props.imageEnvironment}
        imageEnvironmentLoading={props.imageEnvironmentLoading}
        open={controller.exportWizardOpen}
        options={props.options}
        platformOptionsForSourceEnv={state.platformOptionsForSourceEnv}
        platformServices={state.platformServices}
        preview={props.preview}
        previewing={props.previewing}
        productVersion={state.productVersion}
        projectKey={state.projectKey}
        selectedBusinessOptions={state.selectedBusinessOptions}
        selectedDatabaseOption={state.selectedDatabaseOption}
        selectedPlatformOptions={state.selectedPlatformOptions}
        selectedProject={state.selectedProject}
        sourceEnv={state.sourceEnv}
        step={controller.exportStep}
        targetDraft={state.targetDraft}
        onBuild={() => void controller.buildPackage()}
        onBusinessChange={controller.onBusinessChange}
        onCancel={() => controller.setExportWizardOpen(false)}
        onDatabaseChange={state.setDatabase}
        onDeployModeChange={state.setDeployMode}
        onNext={() => void controller.goNextExportStep()}
        onPlatformChange={controller.onPlatformChange}
        onPrevious={controller.goPreviousExportStep}
        onProductVersionChange={state.setProductVersion}
        onProjectChange={state.applyProjectDefaults}
        onRefreshMicroservices={() => void controller.refreshMicroserviceDeliveries()}
        onRefreshPreview={props.onRefreshPreview}
        onRequiredPlatformClick={controller.onRequiredPlatformClick}
        onSourceEnvChange={state.setSourceEnv}
        onTargetDraftChange={state.setTargetDraft}
        refreshingMicroservices={controller.refreshingMicroservices}
      />
      <BusinessPlatformRegistrationModal form={props.registerForm} loading={controller.registeringBusiness} open={controller.registerModalOpen} options={props.options} onCancel={() => controller.setRegisterModalOpen(false)} onSubmit={() => void controller.submitBusinessRegistration()} />
    </>
  );
}
