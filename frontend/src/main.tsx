import React from "react";
import { createRoot } from "react-dom/client";
import { App as AntApp, ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import { Tabs } from "antd";
import "remixicon/fonts/remixicon.css";
import "./styles/global.css";
import { DeploymentPackageExportView } from "./views/DeploymentPackageExportView";
import { MicroserviceRegistrationView } from "./views/MicroserviceRegistrationView";
import { SystemSettingsView } from "./views/SystemSettingsView";

const appItems = [
  {
    key: "deployment-packages",
    label: "部署包工厂",
    children: <DeploymentPackageExportView />,
  },
  {
    key: "microservices",
    label: "微服务注册",
    children: (
      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>微服务注册</h2>
            <p>选择业务平台并生成可 clone 的微服务项目骨架</p>
          </div>
        </div>
        <div className="panel-body">
          <MicroserviceRegistrationView />
        </div>
      </section>
    ),
  },
  {
    key: "settings",
    label: "系统设置",
    children: (
      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>系统设置</h2>
            <p>维护 Git、Harbor、Jenkins 等公共环境信息</p>
          </div>
        </div>
        <div className="panel-body">
          <SystemSettingsView />
        </div>
      </section>
    ),
  },
];

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN}>
      <AntApp>
        <Tabs className="app-tabs" items={appItems} />
      </AntApp>
    </ConfigProvider>
  </React.StrictMode>,
);
