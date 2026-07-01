import type { FormInstance } from "antd";
import type { DeploymentPackageOptions, DeploymentServiceOption } from "../../../api/deploymentPackages";
import type { MicroserviceScaffoldOptions } from "../../../api/microservices";
import type { SystemSettings } from "../../../api/settings";
import type { MicroserviceWizardValues } from "../../hooks/useMicroserviceRegistration";

export interface MicroserviceWizardStepProps {
  businessPlatforms: DeploymentServiceOption[];
  deploymentOptions: DeploymentPackageOptions | null;
  form: FormInstance<MicroserviceWizardValues>;
  formValues: MicroserviceWizardValues;
  options: MicroserviceScaffoldOptions | null;
  selectedPlatform?: DeploymentServiceOption;
  systemSettings: SystemSettings | null;
  onValuesChange: (changed: Partial<MicroserviceWizardValues> | null, values: MicroserviceWizardValues) => void;
}
