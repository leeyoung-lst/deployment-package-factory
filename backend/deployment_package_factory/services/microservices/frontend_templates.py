from __future__ import annotations

from pathlib import PurePosixPath

from deployment_package_factory.services.microservices.templates_common import TemplateFile


def render_frontend_files(context: dict[str, object]) -> list[TemplateFile]:
    stack = str(context["tech_stack"])
    main, index, main_path = _entry_files(context, stack)
    files = [
        TemplateFile(PurePosixPath("package.json"), frontend_package(context)),
        TemplateFile(PurePosixPath("tsconfig.json"), frontend_tsconfig()),
        TemplateFile(PurePosixPath("vite.config.ts"), frontend_vite_config(context)),
        TemplateFile(PurePosixPath("index.html"), index),
        TemplateFile(PurePosixPath(main_path), main),
        TemplateFile(PurePosixPath("src/style.css"), "body { margin: 0; font-family: Inter, 'Microsoft YaHei', sans-serif; }\n"),
    ]
    if stack != "react-vite":
        files.extend(_vue_app_files(context))
    return files


def frontend_required_files(tech_stack: str) -> list[str]:
    files = ["package.json", "index.html", "vite.config.ts", "tsconfig.json"]
    if tech_stack == "react-vite":
        return [*files, "src/main.tsx"]
    return [*files, "src/main.ts", "src/router/index.ts", "src/App.vue"]


def frontend_package(context: dict[str, object]) -> str:
    stack = context["tech_stack"]
    deps = _react_dependencies() if stack == "react-vite" else _vue_dependencies()
    extra = _micro_frontend_dependency(str(context.get("micro_frontend_framework") or ""), stack)
    return f'{{"name":"{context["service_key"]}","type":"module","scripts":{{"build":"vite build","dev":"vite --host 0.0.0.0"}},"dependencies":{{{deps}{extra}}},"devDependencies":{{}}}}\n'


def frontend_tsconfig() -> str:
    return '{"compilerOptions":{"target":"ES2022","module":"ESNext","moduleResolution":"Bundler","strict":true,"jsx":"react-jsx","skipLibCheck":true},"include":["src","vite.config.ts"]}\n'


def frontend_vite_config(context: dict[str, object]) -> str:
    plugin = "react from '@vitejs/plugin-react'" if context["tech_stack"] == "react-vite" else "vue from '@vitejs/plugin-vue'"
    use_plugin = "react()" if context["tech_stack"] == "react-vite" else "vue()"
    return f"import {{ defineConfig }} from 'vite';\nimport {plugin};\n\nexport default defineConfig({{ plugins: [{use_plugin}], server: {{ host: '0.0.0.0', port: {context['port']} }} }});\n"


def _entry_files(context: dict[str, object], stack: str) -> tuple[str, str, str]:
    if stack == "react-vite":
        main = "import React from 'react';\nimport { createRoot } from 'react-dom/client';\nimport { Button } from 'antd';\nimport 'antd/dist/reset.css';\nimport './style.css';\ncreateRoot(document.getElementById('root')!).render(<Button type=\"primary\">Hello {service}</Button>);\n"
        return main.replace("{service}", str(context["service_name"])), '<div id="root"></div><script type="module" src="/src/main.tsx"></script>\n', "src/main.tsx"
    main = "import { createApp } from 'vue';\nimport ElementPlus from 'element-plus';\nimport 'element-plus/dist/index.css';\nimport App from './App.vue';\nimport router from './router';\nimport './style.css';\ncreateApp(App).use(router).use(ElementPlus).mount('#app');\n"
    return main, '<div id="app"></div><script type="module" src="/src/main.ts"></script>\n', "src/main.ts"


def _vue_app_files(context: dict[str, object]) -> list[TemplateFile]:
    return [
        TemplateFile(PurePosixPath("src/router/index.ts"), "import { createRouter, createWebHistory } from 'vue-router';\nexport default createRouter({ history: createWebHistory(), routes: [{ path: '/', component: { template: '<main>微服务前端骨架</main>' } }] });\n"),
        TemplateFile(PurePosixPath("src/App.vue"), f"<template><main><h1>{context['service_name']}</h1><p>{context['description']}</p></main></template>\n"),
    ]


def _react_dependencies() -> str:
    return '"@vitejs/plugin-react":"^4.3.0","react":"^18.3.1","react-dom":"^18.3.1","antd":"^5.20.0","typescript":"^5.5.0","vite":"^5.4.0"'


def _vue_dependencies() -> str:
    return '"@vitejs/plugin-vue":"^5.1.0","vue":"^3.4.0","vue-router":"^4.4.0","pinia":"^2.2.0","element-plus":"^2.8.0","typescript":"^5.5.0","vite":"^5.4.0"'


def _micro_frontend_dependency(framework: str, stack: object) -> str:
    if framework == "qiankun":
        return ',"qiankun":"^2.10.16"'
    if framework == "wujie" and stack == "react-vite":
        return ',"wujie-react":"^1.0.5"'
    if framework == "wujie":
        return ',"wujie-vue3":"^1.0.22"'
    return ""
