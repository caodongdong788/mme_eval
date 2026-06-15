# 项目级 Skills（`.cursor/skills/`）

本目录下的 skill 是**项目自带**（vendored 为实体目录、随仓库走），用于让本项目「用了哪些 skill」一目了然，并且不依赖各人本机装了什么。Cursor 会扫描 `.cursor/skills/<name>/SKILL.md`，按 skill 的 `description` 在相关任务时**按需触发**。

> 注意：skill ≠ rule。规则（常驻/按 glob 注入）在 `.cursor/rules/*.mdc`；skill 是按需加载的能力，不会出现在 rules 下。

## 清单

| Skill | 用途 | 来源（上游） |
|---|---|---|
| `frontend-design` | 前端 UI/组件/页面实现，产出有设计感、避免「AI 味」的生产级代码 | Claude 插件 `frontend-design` |
| `graphify` | 代码图谱 / 依赖 / 模块 / 风险扫描（工作流要求改码前后刷新图谱） | `~/.claude/skills/graphify` |
| `brainstorming` | 需求澄清 / 设计探索（workflow-lock §3.8：需求有歧义时先澄清） | Superpowers 插件 |
| `writing-plans` | 制定多步实现计划（workflow-lock §3.8：多文件/高风险改动先出计划） | Superpowers 插件 |
| `openspec-propose` | 创建 OpenSpec 变更（proposal/design/specs/tasks 一步生成） | 项目原有 |
| `openspec-explore` | 探索模式：讨论想法、澄清需求 | 项目原有 |
| `openspec-apply-change` | 按 tasks 实施 OpenSpec 变更 | 项目原有 |
| `openspec-archive-change` | 变更完成后校验并归档 | 项目原有 |

> 工作流（`.cursor/rules/workflow-lock.mdc`）依赖以上 `graphify` / `brainstorming` / `writing-plans` / `openspec-*`；`frontend-design` 供本项目偶发的前端产物使用。

## 让 Cursor 扫描到

Skill 在**会话开始时**加载，新增/更新后需要：

1. 命令面板（`Cmd+Shift+P`）→ **Developer: Reload Window**；
2. **新开一个 chat**（当前会话不会热更新）。

## 同步更新（副本不会随上游自动更新）

`.cursor/skills/` 里是**拷贝**，上游插件升级后需手动重拉。在仓库根目录执行：

```bash
SP="$HOME/.cursor/plugins/cache/cursor-public/superpowers"/*/skills
cp -RL "$HOME/.claude/plugins/marketplaces/claude-plugins-official/plugins/frontend-design/skills/frontend-design" .cursor/skills/frontend-design
cp -RL "$HOME/.claude/skills/graphify"        .cursor/skills/graphify
cp -RL $SP/brainstorming                      .cursor/skills/brainstorming
cp -RL $SP/writing-plans                      .cursor/skills/writing-plans
```

> `graphify` / `brainstorming` / `writing-plans` 同时也存在于全局（`~/.claude/skills/` 或 Superpowers 插件缓存），会与本项目副本并存；通常**项目级优先**，功能不受影响。
