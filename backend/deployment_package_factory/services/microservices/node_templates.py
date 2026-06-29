from __future__ import annotations

from pathlib import PurePosixPath

from deployment_package_factory.services.microservices.middleware_plugins import middleware_ts
from deployment_package_factory.services.microservices.templates_common import TemplateFile


def render_nodejs_files(context: dict[str, object]) -> list[TemplateFile]:
    return [
        TemplateFile(PurePosixPath("package.json"), node_package(context)),
        TemplateFile(PurePosixPath("tsconfig.json"), '{"compilerOptions":{"target":"ES2022","module":"NodeNext","moduleResolution":"NodeNext","strict":true,"outDir":"dist","rootDir":"src"},"include":["src"]}\n'),
        TemplateFile(PurePosixPath("src/domain/demo.ts"), domain_model()),
        TemplateFile(PurePosixPath("src/domain/services.ts"), domain_service()),
        TemplateFile(PurePosixPath("src/application/useCases.ts"), application_use_cases()),
        TemplateFile(PurePosixPath("src/config/settings.ts"), settings_file(context)),
        TemplateFile(PurePosixPath("src/infrastructure/logger.ts"), logger_file()),
        TemplateFile(PurePosixPath("src/infrastructure/middleware.ts"), middleware_ts(context["middleware"])),
        TemplateFile(PurePosixPath("src/infrastructure/middlewareClients.ts"), middleware_clients(context)),
        TemplateFile(PurePosixPath("src/interfaces/http/routes.ts"), routes_file()),
        TemplateFile(PurePosixPath("src/interfaces/http/server.ts"), server_file(context)),
        TemplateFile(PurePosixPath("tests/demo.test.ts"), test_file()),
    ]


def node_required_files() -> list[str]:
    return [
        "package.json",
        "src/domain/demo.ts",
        "src/domain/services.ts",
        "src/application/useCases.ts",
        "src/config/settings.ts",
        "src/infrastructure/logger.ts",
        "src/infrastructure/middleware.ts",
        "src/infrastructure/middlewareClients.ts",
        "src/interfaces/http/routes.ts",
        "src/interfaces/http/server.ts",
        "tests/demo.test.ts",
    ]


def node_package(context: dict[str, object]) -> str:
    return f"""{{"name":"{context["service_key"]}","type":"module","scripts":{{"build":"tsc","start":"node dist/interfaces/http/server.js","test":"node --test dist/tests/*.test.js"}},"dependencies":{{"express":"^4.19.2"}},"devDependencies":{{"typescript":"^5.5.0","@types/express":"^4.17.21","@types/node":"^22.0.0"}}}}
"""


def domain_model() -> str:
    return """export interface DemoItem {
  name: string;
  normalizedName: string;
  createdAt: string;
}
"""


def domain_service() -> str:
    return """import type { DemoItem } from './demo.js';

export function createDemoItem(name: string): DemoItem {
  const normalizedName = name.toLowerCase().replace(/[^a-z0-9-]+/g, '-').replace(/^-|-$/g, '') || 'item';
  return { name, normalizedName, createdAt: new Date().toISOString() };
}
"""


def application_use_cases() -> str:
    return """import { createDemoItem } from '../domain/services.js';
import { middlewareHealth } from '../infrastructure/middlewareClients.js';

export const createItem = (name: string) => createDemoItem(name);
export const collectRuntime = () => ({ middleware: middlewareHealth() });
"""


def settings_file(context: dict[str, object]) -> str:
    return f"""export const settings = {{
  serviceName: process.env.SERVICE_NAME || '{context['service_key']}',
  businessPlatformKey: process.env.BUSINESS_PLATFORM_KEY || '{context['business_platform_key']}',
  namespace: process.env.BUSINESS_PLATFORM_NAMESPACE || '{context['business_platform_namespace']}',
  port: Number(process.env.APP_PORT || {context['port']}),
}};
"""


def logger_file() -> str:
    return """export const logger = {
  info: (message: string, extra: Record<string, unknown> = {}) => console.log(JSON.stringify({ level: 'info', message, ...extra })),
  error: (message: string, extra: Record<string, unknown> = {}) => console.error(JSON.stringify({ level: 'error', message, ...extra })),
};
"""


def middleware_clients(context: dict[str, object]) -> str:
    checks = ", ".join(f"{item}: Boolean(process.env.{str(item).upper()}_ENDPOINT)" for item in context["middleware"])
    return f"""export function middlewareHealth() {{
  return {{ {checks} }};
}}
"""


def routes_file() -> str:
    return """import { Router } from 'express';
import { collectRuntime, createItem } from '../../application/useCases.js';

export const router = Router();
router.get('/health', (_, res) => res.json({ status: 'ok' }));
router.get('/runtime', (_, res) => res.json(collectRuntime()));
router.post('/api/v1/items/:name', (req, res) => res.json(createItem(req.params.name)));
"""


def server_file(context: dict[str, object]) -> str:
    return f"""import express from 'express';
import {{ settings }} from '../../config/settings.js';
import {{ logger }} from '../../infrastructure/logger.js';
import {{ router }} from './routes.js';

const app = express();
app.use(express.json());
app.use(router);
app.listen(settings.port, () => logger.info('service started', {{ service: '{context['service_key']}', port: settings.port }}));
"""


def test_file() -> str:
    return """import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createItem } from '../src/application/useCases.js';

test('create item normalizes name', () => {
  assert.equal(createItem('Demo Item').normalizedName, 'demo-item');
});
"""
