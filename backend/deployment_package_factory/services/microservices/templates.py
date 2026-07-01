from __future__ import annotations

from pathlib import PurePosixPath

from deployment_package_factory.services.microservices.middleware_plugins import (
    env_placeholder_lines,
    middleware_catalog,
    middleware_yaml,
)
from deployment_package_factory.services.microservices.node_templates import node_required_files, render_nodejs_files
from deployment_package_factory.services.microservices.templates_common import TemplateFile

PROJECT_KINDS = {
    "backend": "后端微服务",
    "frontend": "前端应用",
}

TECH_STACKS = {
    "python-fastapi": "Python FastAPI",
    "nodejs-express": "Node.js Express",
    "java-spring-cloud-alibaba": "Java Spring Cloud Alibaba + Nacos + JPA",
    "vue3-vite": "Vue3 Vite + Pinia + Router + Element Plus",
    "react-vite": "React Vite + Router + Ant Design",
}

MICRO_FRONTEND_FRAMEWORKS = {
    "qiankun": "Qiankun 微前端",
    "wujie": "Wujie 微前端",
}

TECH_STACK_PROJECT_KIND = {
    "python-fastapi": "backend",
    "nodejs-express": "backend",
    "java-spring-cloud-alibaba": "backend",
    "vue3-vite": "frontend",
    "react-vite": "frontend",
}

MIDDLEWARE = middleware_catalog()


def render_generic_template(request) -> list[TemplateFile]:
    context = _context(request)
    files = _common_files(context)
    stack = request.tech_stack
    if stack == "nodejs-express":
        files.extend(_nodejs_files(context))
    elif stack == "java-spring-cloud-alibaba":
        files.extend(_java_files(context))
    elif stack in {"vue3-vite", "react-vite"}:
        files.extend(_frontend_files(context))
    else:
        raise ValueError(f"Unsupported techStack: {stack}")
    return files


def generic_required_files(tech_stack: str) -> list[str]:
    required = ["README.md", ".env.template", "Dockerfile", "Jenkinsfile", "build.sh", "deploy.sh", "deploy/k8s/deployment.yaml", "deploy/helm"]
    if tech_stack == "nodejs-express":
        required.extend(node_required_files())
    elif tech_stack == "java-spring-cloud-alibaba":
        required.extend(["pom.xml", "src/main/java/com/example/domain/DemoItem.java", "src/main/java/com/example/interfaces/HealthController.java"])
    elif tech_stack == "react-vite":
        required.extend(["package.json", "src/main.tsx"])
    else:
        required.extend(["package.json", "src/main.ts", "src/router/index.ts"])
    return required


def _context(request) -> dict[str, object]:
    image = f"{request.image_registry.rstrip('/')}/{request.image_namespace.strip('/')}/{request.service_key}"
    return {
        "service_key": request.service_key,
        "service_name": request.service_name,
        "description": request.description or request.service_name,
        "tech_stack": request.tech_stack,
        "micro_frontend_framework": request.micro_frontend_framework,
        "port": request.port,
        "middleware": request.middleware,
        "image": image,
        "source_env": request.source_env,
        "business_platform_key": request.business_platform_key,
        "business_platform_namespace": request.business_platform_namespace or request.k8s_namespace or request.business_platform_key,
        "k8s_namespace": request.k8s_namespace or request.business_platform_namespace or request.business_platform_key,
    }


def _common_files(context: dict[str, object]) -> list[TemplateFile]:
    service = str(context["service_key"])
    return [
        TemplateFile(PurePosixPath(".gitignore"), "node_modules/\ntarget/\ndist/\n.env\n*.log\n"),
        TemplateFile(PurePosixPath(".env.template"), _env_template(context)),
        TemplateFile(PurePosixPath("README.md"), _readme(context)),
        TemplateFile(PurePosixPath("Dockerfile"), _dockerfile(context)),
        TemplateFile(PurePosixPath("Jenkinsfile"), _jenkinsfile(context)),
        TemplateFile(PurePosixPath("build.sh"), _build_sh(context), executable=True),
        TemplateFile(PurePosixPath("deploy.sh"), _deploy_sh(context), executable=True),
        TemplateFile(PurePosixPath("deploy/k8s/deployment.yaml"), _k8s_deployment(context)),
        TemplateFile(PurePosixPath("deploy/k8s/service.yaml"), _k8s_service(context)),
        TemplateFile(PurePosixPath(f"deploy/helm/{service}/Chart.yaml"), _helm_chart(context)),
        TemplateFile(PurePosixPath(f"deploy/helm/{service}/values.yaml"), _helm_values(context)),
        TemplateFile(PurePosixPath(f"deploy/helm/{service}/templates/deployment.yaml"), _helm_deployment(context)),
        TemplateFile(PurePosixPath(f"deploy/helm/{service}/templates/service.yaml"), _helm_service(context)),
        TemplateFile(PurePosixPath("config/middleware.example.yaml"), middleware_yaml(context["middleware"])),
    ]


def _nodejs_files(context: dict[str, object]) -> list[TemplateFile]:
    return render_nodejs_files(context)


def _java_files(context: dict[str, object]) -> list[TemplateFile]:
    return [
        TemplateFile(PurePosixPath("pom.xml"), _java_pom(context)),
        TemplateFile(PurePosixPath("src/main/resources/application.yml"), _java_application_yml(context)),
        TemplateFile(PurePosixPath("src/main/java/com/example/domain/DemoItem.java"), "package com.example.domain;\n\npublic record DemoItem(String name, String normalizedName) {}\n"),
        TemplateFile(PurePosixPath("src/main/java/com/example/application/DemoService.java"), "package com.example.application;\n\nimport com.example.domain.DemoItem;\nimport org.springframework.stereotype.Service;\n\n@Service\npublic class DemoService {\n  public DemoItem create(String name) { return new DemoItem(name, name.toLowerCase().replaceAll(\"[^a-z0-9-]+\", \"-\")); }\n}\n"),
        TemplateFile(PurePosixPath("src/main/java/com/example/interfaces/HealthController.java"), _java_controller(context)),
        TemplateFile(PurePosixPath("src/main/java/com/example/Application.java"), _java_main()),
    ]


def _frontend_files(context: dict[str, object]) -> list[TemplateFile]:
    stack = str(context["tech_stack"])
    app_import = "import './style.css';"
    if stack == "react-vite":
        main = "import React from 'react';\nimport { createRoot } from 'react-dom/client';\nimport { Button } from 'antd';\nimport 'antd/dist/reset.css';\nimport './style.css';\ncreateRoot(document.getElementById('root')!).render(<Button type=\"primary\">Hello {service}</Button>);\n".replace("{service}", str(context["service_name"]))
        index = '<div id="root"></div><script type="module" src="/src/main.tsx"></script>\n'
        main_path = "src/main.tsx"
    else:
        main = "import { createApp } from 'vue';\nimport ElementPlus from 'element-plus';\nimport 'element-plus/dist/index.css';\nimport App from './App.vue';\nimport router from './router';\nimport './style.css';\ncreateApp(App).use(router).use(ElementPlus).mount('#app');\n"
        index = '<div id="app"></div><script type="module" src="/src/main.ts"></script>\n'
        main_path = "src/main.ts"
    files = [
        TemplateFile(PurePosixPath("package.json"), _frontend_package(context)),
        TemplateFile(PurePosixPath("index.html"), index),
        TemplateFile(PurePosixPath(main_path), main),
        TemplateFile(PurePosixPath("src/router/index.ts"), "import { createRouter, createWebHistory } from 'vue-router';\nexport default createRouter({ history: createWebHistory(), routes: [{ path: '/', component: { template: '<main>微服务前端骨架</main>' } }] });\n"),
        TemplateFile(PurePosixPath("src/style.css"), "body { margin: 0; font-family: Inter, 'Microsoft YaHei', sans-serif; }\n"),
    ]
    if stack != "react-vite":
        files.append(TemplateFile(PurePosixPath("src/App.vue"), f"<template><main><h1>{context['service_name']}</h1><p>{context['description']}</p></main></template>\n"))
    return files


def _env_template(context: dict[str, object]) -> str:
    lines = [f"SERVICE_NAME={context['service_key']}", f"BUSINESS_PLATFORM_KEY={context['business_platform_key']}", f"BUSINESS_PLATFORM_NAMESPACE={context['business_platform_namespace']}", f"APP_PORT={context['port']}"]
    lines.extend(env_placeholder_lines(context["middleware"]))
    return "\n".join(lines) + "\n"


def _readme(context: dict[str, object]) -> str:
    return f"""# {context['service_name']}

{context['description']}

- Tech stack: {context['tech_stack']}
- Business platform: {context['business_platform_key']}
- Namespace: {context['k8s_namespace']}
- Middleware: {', '.join(context['middleware']) or 'none'}

## Run

```bash
./build.sh
./deploy.sh {context['image']}:dev
```
"""


def _dockerfile(context: dict[str, object]) -> str:
    stack = context["tech_stack"]
    if stack == "java-spring-cloud-alibaba":
        return "FROM eclipse-temurin:21-jre\nWORKDIR /app\nCOPY target/*.jar app.jar\nUSER 10001\nENTRYPOINT [\"java\",\"-jar\",\"/app/app.jar\"]\n"
    if stack in {"vue3-vite", "react-vite"}:
        return "FROM nginx:1.27-alpine\nCOPY dist /usr/share/nginx/html\nUSER 101\n"
    return f"FROM node:22-alpine\nWORKDIR /app\nCOPY package*.json ./\nRUN npm install\nCOPY . .\nRUN npm run build\nUSER node\nEXPOSE {context['port']}\nCMD [\"npm\",\"start\"]\n"


def _jenkinsfile(context: dict[str, object]) -> str:
    return f"""pipeline {{
  agent any
  environment {{ IMAGE = "{context['image']}:${{env.BUILD_NUMBER}}" }}
  stages {{
    stage('Build') {{ steps {{ sh './build.sh $IMAGE' }} }}
    stage('Deploy') {{ steps {{ sh './deploy.sh $IMAGE' }} }}
  }}
}}
"""


def _build_sh(context: dict[str, object]) -> str:
    stack = context["tech_stack"]
    command = "mvn -q -DskipTests package" if stack == "java-spring-cloud-alibaba" else "npm install && npm run build"
    return f"#!/usr/bin/env bash\nset -euo pipefail\nIMAGE=\"${{1:-{context['image']}:dev}}\"\n{command}\ndocker build -t \"${{IMAGE}}\" .\n"


def _deploy_sh(context: dict[str, object]) -> str:
    service = context["service_key"]
    return f"#!/usr/bin/env bash\nset -euo pipefail\nIMAGE=\"${{1:-{context['image']}:dev}}\"\nhelm upgrade --install {service} deploy/helm/{service} --namespace {context['k8s_namespace']} --create-namespace --set image.repository=\"${{IMAGE%:*}}\" --set image.tag=\"${{IMAGE##*:}}\"\n"


def _k8s_deployment(context: dict[str, object]) -> str:
    return f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {context['service_key']}
  namespace: {context['k8s_namespace']}
spec:
  replicas: 1
  selector:
    matchLabels: {{ app: {context['service_key']} }}
  template:
    metadata:
      labels:
        app: {context['service_key']}
        business-platform: {context['business_platform_key']}
    spec:
      containers:
        - name: {context['service_key']}
          image: {context['image']}:latest
          ports:
            - containerPort: {context['port']}
"""


def _k8s_service(context: dict[str, object]) -> str:
    return f"apiVersion: v1\nkind: Service\nmetadata:\n  name: {context['service_key']}\n  namespace: {context['k8s_namespace']}\nspec:\n  selector:\n    app: {context['service_key']}\n  ports:\n    - port: 80\n      targetPort: {context['port']}\n"


def _helm_chart(context: dict[str, object]) -> str:
    return f"apiVersion: v2\nname: {context['service_key']}\ntype: application\nversion: 0.1.0\nappVersion: \"0.1.0\"\n"


def _helm_values(context: dict[str, object]) -> str:
    return f"image:\n  repository: {context['image']}\n  tag: latest\nservice:\n  port: 80\n  targetPort: {context['port']}\n"


def _helm_deployment(context: dict[str, object]) -> str:
    return f"apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: {context['service_key']}\nspec:\n  selector:\n    matchLabels:\n      app: {context['service_key']}\n  template:\n    metadata:\n      labels:\n        app: {context['service_key']}\n    spec:\n      containers:\n        - name: {context['service_key']}\n          image: \"{{{{ .Values.image.repository }}}}:{{{{ .Values.image.tag }}}}\"\n          ports:\n            - containerPort: {{{{ .Values.service.targetPort }}}}\n"


def _helm_service(context: dict[str, object]) -> str:
    return f"apiVersion: v1\nkind: Service\nmetadata:\n  name: {context['service_key']}\nspec:\n  selector:\n    app: {context['service_key']}\n  ports:\n    - port: {{{{ .Values.service.port }}}}\n      targetPort: {{{{ .Values.service.targetPort }}}}\n"


def _java_pom(context: dict[str, object]) -> str:
    return f"""<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion><groupId>com.example</groupId><artifactId>{context['service_key']}</artifactId><version>0.1.0</version><properties><java.version>21</java.version><spring-boot.version>3.3.0</spring-boot.version></properties><dependencies><dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-web</artifactId><version>${{spring-boot.version}}</version></dependency><dependency><groupId>com.alibaba.cloud</groupId><artifactId>spring-cloud-starter-alibaba-nacos-discovery</artifactId><version>2023.0.1.0</version></dependency><dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-data-jpa</artifactId><version>${{spring-boot.version}}</version></dependency></dependencies><build><plugins><plugin><groupId>org.springframework.boot</groupId><artifactId>spring-boot-maven-plugin</artifactId><version>${{spring-boot.version}}</version></plugin></plugins></build></project>\n"""


def _java_application_yml(context: dict[str, object]) -> str:
    return f"server:\n  port: {context['port']}\nspring:\n  application:\n    name: {context['service_key']}\n  cloud:\n    nacos:\n      discovery:\n        server-addr: ${{NACOS_ENDPOINT:localhost:8848}}\n"


def _java_main() -> str:
    return "package com.example;\n\nimport org.springframework.boot.SpringApplication;\nimport org.springframework.boot.autoconfigure.SpringBootApplication;\n\n@SpringBootApplication\npublic class Application { public static void main(String[] args) { SpringApplication.run(Application.class, args); } }\n"


def _java_controller(context: dict[str, object]) -> str:
    return "package com.example.interfaces;\n\nimport com.example.application.DemoService;\nimport org.springframework.web.bind.annotation.*;\n\n@RestController\npublic class HealthController {\n  private final DemoService demoService;\n  public HealthController(DemoService demoService) { this.demoService = demoService; }\n  @GetMapping(\"/health\") public Object health() { return java.util.Map.of(\"status\", \"ok\"); }\n  @PostMapping(\"/api/v1/items/{name}\") public Object create(@PathVariable String name) { return demoService.create(name); }\n}\n"


def _frontend_package(context: dict[str, object]) -> str:
    stack = context["tech_stack"]
    deps = '"@vitejs/plugin-react":"^4.3.0","react":"^18.3.1","react-dom":"^18.3.1","antd":"^5.20.0","typescript":"^5.5.0","vite":"^5.4.0"' if stack == "react-vite" else '"@vitejs/plugin-vue":"^5.1.0","vue":"^3.4.0","vue-router":"^4.4.0","pinia":"^2.2.0","element-plus":"^2.8.0","typescript":"^5.5.0","vite":"^5.4.0"'
    framework = context.get("micro_frontend_framework")
    extra = ',"qiankun":"^2.10.16"' if framework == "qiankun" else ',"wujie-vue3":"^1.0.22"' if framework == "wujie" else ""
    return f'{{"name":"{context["service_key"]}","type":"module","scripts":{{"build":"vite build","dev":"vite --host 0.0.0.0"}},"dependencies":{{{deps}{extra}}},"devDependencies":{{}}}}\n'
