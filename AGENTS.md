# PROJECT CODE-X DEVELOPMENT MATRIX & AGENT GUIDANCE

> Context: Governs Codex Desktop App threads in this repository.
> Enforcement: Mandatory for code generation, file modification, and diffs.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, invoke the `skill` tool with `skill: "graphify"` before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` when practical to keep the graph current (AST-only, no API cost).

## PART 1: Frontend UX Constraints

- Rule of 4: A single page or single form region must not expose more than 4 user inputs such as Input, Select, Radio, Checkbox group, DatePicker, or Upload.
- Mandatory wizarding: If a workflow requires more than 4 business fields, split it into steps, tabs, or a wizard. Do not build one-page endless forms.
- Component size: A single frontend component file (`.tsx` / `.vue`) must stay within 150 physical lines. If it exceeds the limit, split local UI into files under a nearby `components/` directory.
- Defensive interactions: Next, submit, save, and destructive action buttons must be disabled when the current step is invalid or an async action is running. All async behavior must expose a loading state.
- Logic/UI separation with custom hooks: Complex `onSubmit`, cross-field `onChange`, state transitions, API calls, polling, retries, and error handling must be extracted to a sibling `hooks/use[ModuleName].ts`. Component files should only contain rendering, light event binding, and presentation state.
- No inline sub-components: Do not define sub-components inside the same file with patterns such as `const SubComponent = () => { ... }`. Extracted components must live in independent physical files; inline JSX/helper functions still count toward the 150-line limit.

## PART 2: Backend DDD Constraints

- Four-layer direction: New backend business code should preserve clear Interfaces, Application, Domain, and Infrastructure boundaries. When changing legacy code, do not widen existing architecture debt.
- Rich domain model: Business validation, state transitions, and reusable business rules should live in Domain entities or Domain services instead of being duplicated in API handlers or persistence code.
- Backend size limits: A backend class/file must stay within 250 physical lines where practical; a single method/function should stay within 30 lines and keep one responsibility.
- Domain purity: Domain code must not import Infrastructure, ORM/database models, web frameworks, message queues, Kubernetes/external SDK clients, or other framework-specific dependencies. Database mappings, API schemas, persistence DO/PO objects, and external DTOs belong in Infrastructure or Interfaces and must be converted to Domain entities through mappers/repositories.
- Repository pattern: Application code must not directly call Mapper/DAO/ORM models. Use Repository interfaces defined at the Domain boundary; concrete persistence implementations belong in Infrastructure.
- No cross-Application leaks: Application services must not call one another just to reuse business logic. Shared business behavior must be moved into Domain entity methods, Domain services, or a Shared Kernel.

## PART 3: Codex Agent Execution Protocol

Before producing code, modifying files, or providing a diff for a substantial change, start the response with this Chinese self-check block:

```markdown
### CODE-X ARCHITECTURE SELF-CHECK
- **图谱依赖**：[说明是否使用 graphify；若未使用，说明本次任务为什么不需要图谱]
- **图谱防线**：[若涉及核心代码，说明通过 `graphify query` / `graphify explain` / `graphify affected` 查到的影响面；列出最多 2 个最相关的上游/下游节点，并确认本次修改不会破坏其调用契约]
- **UX交互方案**：[若涉及前端，说明如何满足 Rule of 4、步骤拆分、loading/disabled 和组件行数限制；不涉及则写“不涉及前端”]
- **DDD聚合根**：[若涉及后端业务规则，说明规则内聚在哪个 Domain 实体或 Domain Service；不涉及则写“不涉及后端业务规则”]
- **物理行数预算**：[确认新增或修改文件是否满足 150/250 行限制；如触及历史超限文件，说明是否拆分或为什么本次不扩大债务]
```

For small factual answers, terminal-only checks, or documentation-only discussion, keep the answer concise and do not manufacture irrelevant DDD or UX claims.
