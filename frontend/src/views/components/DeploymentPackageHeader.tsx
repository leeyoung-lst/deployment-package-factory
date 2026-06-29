import React from "react";
import { Button, Space } from "antd";

interface Props {
  building: boolean;
  imageEnvironmentLoading: boolean;
  loadingOptions: boolean;
  tasksLoading: boolean;
  onBuild: () => void;
  onRefreshImageEnvironment: () => void;
  onRefreshOptions: () => void;
  onRefreshTasks: () => void;
  onRegisterBusiness: () => void;
}

export function DeploymentPackageHeader(props: Props) {
  return (
    <div className="panel-header">
      <div>
        <h2>部署包工厂</h2>
        <p>管理业务平台 namespace，并按真实环境镜像生成生产部署包</p>
      </div>
      <Space>
        <Button icon={<i className="ri-list-check-3" />} loading={props.tasksLoading} onClick={props.onRefreshTasks}>刷新任务</Button>
        <Button icon={<i className="ri-hard-drive-2-line" />} loading={props.imageEnvironmentLoading} onClick={props.onRefreshImageEnvironment}>检查镜像环境</Button>
        <Button icon={<i className="ri-refresh-line" />} loading={props.loadingOptions} onClick={props.onRefreshOptions}>刷新选项</Button>
        <Button icon={<i className="ri-add-circle-line" />} onClick={props.onRegisterBusiness}>注册业务平台</Button>
        <Button type="primary" icon={<i className="ri-package-line" />} loading={props.building} onClick={props.onBuild}>创建导包任务</Button>
      </Space>
    </div>
  );
}
