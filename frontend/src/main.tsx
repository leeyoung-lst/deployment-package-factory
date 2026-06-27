import React from "react";
import { createRoot } from "react-dom/client";
import { App as AntApp, ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import "remixicon/fonts/remixicon.css";
import "./styles/global.css";
import { DeploymentPackageExportView } from "./views/DeploymentPackageExportView";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN}>
      <AntApp>
        <DeploymentPackageExportView />
      </AntApp>
    </ConfigProvider>
  </React.StrictMode>,
);
