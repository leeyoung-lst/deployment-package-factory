## 1. 核心技术与工具
- **UI 组件库**: 采用 `antd` (v6.4.3) 作为核心 UI 框架，提供基础交互组件（Button, Tabs, Form, Select 等）。
- **图标系统**: 使用 `remixicon` (v4.6.0) 字体图标库，通过 `<i className="ri-*" />` 方式在组件中引用。
- **CSS 方案**: 采用 **CSS Modules** (`.module.css`) 结合原生 CSS。全局样式定义在 `global.css`，组件级样式隔离在各视图的 `.module.css` 文件中。
- **构建工具**: 基于 `Vite` (v7.1.2) 进行开发与构建，支持快速热更新。
- **语言环境**: 通过 `ConfigProvider` 全局配置为中文 (`zh_CN`)。

## 2. 关键文件与目录
- `frontend/src/styles/global.css`: 定义全局设计令牌（Design Tokens），如 `--border-color`, `--text-muted`，以及基础重置和布局类（`.panel`, `.panel-header`）。
- `frontend/src/main.tsx`: 应用入口，挂载 `ConfigProvider` 和 `App` 容器，引入全局样式。
- `frontend/src/views/*.module.css`: 各业务视图的模块化样式文件，采用 Grid/Flex 布局实现响应式设计。
- `frontend/src/views/components/DeploymentDependencyGraph.tsx`: 展示了如何通过内联样式与 CSS Modules 结合实现复杂的 SVG 依赖关系图可视化。

## 3. 架构与设计约定
### 3.1 布局策略
- **面板化布局 (Panel Layout)**: 页面主体通常包裹在 `.panel` 容器中，包含 `.panel-header`（标题与操作区）和 `.panel-body`（内容区）。
- **网格系统 (Grid System)**: 大量使用 CSS Grid (`display: grid`) 进行复杂排版，如双栏布局 (`grid-template-columns: minmax(380px, 520px) 1fr`) 和多列卡片展示。
- **响应式断点**: 定义了 `1120px` 和 `720px` 两个主要断点。在小屏幕下，多列网格自动退化为单列，Flex 容器方向调整为 `column`。

### 3.2 视觉风格
- **色彩体系**: 
  - 背景色: `#f6f7fb` (全局), `rgba(255, 255, 255, 0.82)` (面板/卡片)。
  - 主色调: 蓝色系 (`#1d4ed8`, `#2563eb`) 用于强调和操作。
  - 状态色: 绿色 (`#15803d`) 表示成功，红色 (`#b91c1c`) 表示错误或危险。
- **质感**: 广泛使用半透明背景 (`rgba`) 和细微边框 (`1px solid var(--border-color)`) 营造轻量、现代的 B 端界面风格。
- **字体**: 优先使用 `Inter` 和 `Microsoft YaHei`，代码片段使用 `JetBrains Mono` 或 `Fira Code`。

### 3.3 组件样式规范
- **局部作用域**: 所有视图级组件必须使用 CSS Modules 避免样式冲突。
- **语义化类名**: 类名倾向于描述功能或结构，如 `.wizardSteps`, `.serviceGrid`, `.deliveryItem`。
- **图标集成**: 统一使用 RemixIcon 类名，并在必要时通过 CSS 设置图标容器的背景色和圆角以形成“图标按钮”视觉效果。

## 4. 开发者指南
- **新增页面**: 创建对应的 `.module.css` 文件，并复用 `global.css` 中的 `.panel` 结构以保持整体一致性。
- **响应式适配**: 在编写 Grid 布局时，应同步考虑 `@media (max-width: 720px)` 下的单列表现。
- **主题定制**: 若需调整全局色系，应优先修改 `global.css` 中的 CSS 变量，而非硬编码颜色值。
- **图标使用**: 从 RemixIcon 官网选取图标后，直接使用对应的 `ri-` 前缀类名，无需额外导入 SVG 文件。