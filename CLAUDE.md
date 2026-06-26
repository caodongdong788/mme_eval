# CLAUDE.md

> 本文件让 **Claude Code** 复用本仓库既有的 Cursor 约定。Claude Code 不会自动读取
> `.cursor/rules/*.mdc`，因此这里把项目知识库与 `alwaysApply` 规则用 `@` 显式桥接进来。
> 维护时只改源文件（`AGENTS.md` / `.cursor/rules/*.mdc`），本文件只放引用与桥接说明。

## 项目知识库（导航与约定速查）

@AGENTS.md

## 始终生效的规则（镜像 Cursor 的 `alwaysApply: true`）

下列规则在 Cursor 中 `alwaysApply: true`，对 Claude Code 同样**始终遵守**：

@.cursor/rules/workflow-lock.mdc
@.cursor/rules/respond-in-chinese.mdc
@.cursor/rules/ponytail.mdc
@.cursor/rules/graphify.mdc

## 按目录生效的规则（Cursor glob 规则，Claude Code 需按需读取）

Claude Code 不支持按文件路径条件加载，故以下两条**不**自动导入；**在动到对应目录前 MUST 先读**：

- 改动 `frontend/**`（`.ts/.tsx/.css/.html`）前 → 读 `.cursor/rules/frontend-workflow.mdc`（前端固定流程与自审，收尾 `npm run verify`）。
- 改动 `server/**`（`.py`）前 → 读 `.cursor/rules/server-backend.mdc`（Router → Service → ORM，分页/投影/异常口径）。

## workflow-lock hook（已迁移到 Claude Code）

`.cursor/hooks.json` 是 Cursor 专用，对 Claude Code 不生效。等价的强制检查已迁到
`.claude/settings.json` 的 PreToolUse hook（脚本 `.claude/hooks/workflow-lock-check.sh`）：
改动受治理代码面（`medeval/ tests/ cases/` 下 `.py/.yaml` 或根 `config.yaml`）而
`openspec/changes/` 下无进行中变更时，会要求确认——逻辑与 `workflow-lock.mdc` 一致，fail-open。
