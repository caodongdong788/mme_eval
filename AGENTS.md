# AGENTS.md — MME / medeval 项目知识库

> 给在本仓库工作的 AI agent 的**导航与约定速查**。详尽参考（架构数据流图、用例 YAML 字段、目录结构、评分细节）见 `README.md`；本文件只保留 agent 必须遵守 / 高频用到的内容。

## 1. 项目背景

本仓库 = **判分内核 medeval**（CLI / Python 包）+ **MME · Agent 评测平台**（`server/` + `frontend/`）。

| 组件 | 一句话 | 详读 |
|------|--------|------|
| medeval | YAML 用例 → bot → 三层 judge → 报告；编排核 `medeval/service.py::evaluate()` | [`README.md`](README.md) |
| 评测平台 | Web 发起评测、落库、看板、重判/续跑、HITL、Pairwise、飞书 SSO | [`server/README.md`](server/README.md) + `openspec/specs/eval-platform-*` |
| 用例库 | 乳腺癌专科 benchmark，`cases/breast_cancer/` 共 105 题 | [`cases/README.md`](cases/README.md) |

- **入口**：CLI / 包名 `medeval`；平台后端 `server.app:app`。
- **判分基调**：医疗保守（HardGate fail → 安全/合规归零；LLM 分歧取低分）。完整评分表见 [`README.md`「四模块怎么算」](README.md#核心设计)。

## 2. 项目固定开发流程（强制执行，不可跳步）

> 权威定义见 `.cursor/rules/workflow-lock.mdc`（`alwaysApply`）。本节为跨工具统一口径速查。配套工具：**Graphify | OpenSpec | Superpowers | Ponytail | CodeRabbit**。

所有任务分「**Bug 修复**」「**新功能需求**」两大类，AI 自动判定并执行对应流程。

**Bug 修复分流（权威细则见 workflow-lock.mdc §4.2）**：

| 类型 | 条件 | 流程 |
|------|------|------|
| **轻量 Bug** | 代码净变动 **&lt; 100 行** + 未触及 HardGate / 核心节点 / 主链路口径等禁豁免项 | **精简流程**：一行开场 → 修码 → 触达域验证 → §4.3 精简合规报告；**可跳过** OpenSpec / Graphify / **Cursor Plan** / 子 Agent 审查 |
| **复杂 Bug** | ≥100 行、多文件、根因未明、触及禁豁免项等（§2） | **完整 Bug 链路** + **必须先 Cursor Plan Mode**（§3.0） |
| **标准 Bug** | 其余非轻量 | **完整 Bug 链路** |

**新功能**：一律 **完整链路** + **必须先 Cursor Plan Mode**（§3.0）。

**②澄清 / ③计划 / ④ Plan（速查）**——详见 `workflow-lock.mdc` §1.1：

| 项 | 能力 | 路径 |
|----|------|------|
| ②澄清 | Superpowers **brainstorming** | `.cursor/skills/brainstorming/SKILL.md` |
| ③计划（大/复杂） | Superpowers **writing-plans** | `.cursor/skills/writing-plans/SKILL.md` |
| ③计划（S/M） | OpenSpec **proposal + tasks** | `openspec/changes/<name>/` |
| ④ Plan | **Cursor Plan Mode**（Shift+Tab；编码前用户确认） | [Cursor 文档](https://cursor.com/docs/agent/plan-mode) |

> 新功能**无**小改动豁免，一律完整流程 + Plan。

**工具定位**

1. **Graphify**：代码结构、依赖、模块、风险扫描。每次任务**启动 & 结束必更新**（`graphify . --update`，改码后刷新图谱）。
2. **OpenSpec**：全生命周期文档、变更追溯、设计契约。
3. **Superpowers**：需求澄清、计划、TDD、排障、测试、验证。**澄清/计划已分级硬绑定**（见 workflow-lock.mdc §3.9）：需求有歧义 MUST 先用 `brainstorming` 澄清（无歧义可跳并在开场自检注明）；多文件/动核心节点/高风险改动 MUST 先用 `writing-plans` 出计划，S/M 改动可由 `proposal+tasks` 充当。
4. **Ponytail**：编码前梯子（`ponytail.mdc`）；验证后 **子 Agent** 强制 `ponytail-review`（父 Agent 禁止自审过工程化）。
5. **CodeRabbit**：`git commit` 前由**另一子 Agent** 执行 CLI 审查（父 Agent 禁止自解读 diff 顶替）。

**关键目录**：代码图谱 `graphify-out/`｜变更文档 `openspec/changes/`｜全局规则 `.cursor/rules/`

**固定启动方式**：用户仅需发送【启动指令 + 任务描述】；AI 自动分流，**开场**汇报完整链路 + 流程自检 + 前后端规范触达，**收尾**输出合规报告（模板见 `workflow-lock.mdc` §1 / §5）。

**Bug 修复链路**：刷新图谱 → … → 验证 → **子 Agent ponytail-review** → **子 Agent CodeRabbit** → 图谱 → 归档  
**新功能链路**：刷新图谱 → … → 验收 → **子 Agent ponytail-review** → **子 Agent CodeRabbit** → 图谱 → 归档

**全程铁律**：改代码必更新 Graphify 图谱（**轻量 Bug §4.2 豁免**除外）；任务完成须 OpenSpec 归档（**轻量 Bug 豁免**除外）；**每次 `git commit` 前**须子 Agent ponytail-review + CodeRabbit（**轻量 Bug 未 commit 时可豁免 5a/5b，一旦 commit 仍建议补审**）；禁止无设计、无测试直接编码（**轻量 Bug 须跑触达域验证**）；触及核心节点必查依赖与循环导入。

## 3. 五层架构与评分口径

五层：`Schema → Cases → Runner → Judges → Reporter`（详见 [`README.md`「核心设计」](README.md#核心设计) 与数据流图）。

Agent 改码前 MUST 知晓的要点：

- **三根轴**：`hard_gate_passed` / `gate_passed`（judging）/ `release_passed`（报告层）——赋值点各不同，禁止混用。
- **profile 自适应权重**：每条用例按 YAML `score_profile` 解析 `module_max` 与 `pass_rule`（含 `population` / `agent`）；default 权重 S0.35/C0.08/F0.37/E0.20，勿写死旧口径。
- **语义裁决器**：仅 Rule FAIL 可救回、每题最多 1 条、禁救处方/治愈 must_not、绝不碰 `hard_gate.*`、红旗用例不自动救回（见 §5）。
- **scoring_points**：总扣分×0.1 扣功能分（只减不加）；红旗漏判综合分 cap 0.49。
- **Pairwise**：`PairwiseComparator` 独立于 `BaseJudge`，不写任何 gate 字段；平台见 `server/pairwise_job.py`。
- **aggregator 勿混用**：`judges/aggregator`（CaseResult）vs `reporter/aggregator`（RunReport）——对照表见下。

### 3.1 aggregator 命名对照（勿混用）

仓库内有两个 **aggregator**，职责正交、导入路径不同：

| 模块 | 路径 | 输入 → 输出 | 核心职责 |
|------|------|-------------|----------|
| **判分聚合器** | `medeval/judges/aggregator.py` | `TestCase` + traces → `CaseResult` | 调度各 `BaseJudge`；`verdict_facts()` 单遍历产出 `DerivedFacts`；赋值 `hard_gate_passed` / `gate_passed` / `per_run_gate_passed` |
| **报告聚合器** | `medeval/reporter/aggregator.py` | `CaseResult[]` → `RunReport` | 调用 `scoring.apply_grading` 赋 `release_passed`；汇总 latency / token / 分维度切片 / diff 元数据 |

触及「aggregator」时 MUST 先确认是判分层还是报告层；禁止在两处各自重遍历 verdict（报告层 MUST 消费 `judges/aggregator.verdict_facts` 或 `CaseResult` 已物化字段）。

## 4. 常用命令

```bash
# 判分内核 CLI
pip install -e ".[dev,llm-openai]"                   # 安装（开发模式）
medeval run --config config.yaml                     # 跑评测；落 outputs/<run.name>_<YYYY-MM-DD>_<毫秒时间戳>/（含 traces.jsonl.gz），默认与上一次 diff
medeval run --config config.yaml --repeat 3          # baseline：N=3 majority voting
medeval run --config config.yaml --resume <run目录>   # 断点续跑：复用成功留痕，仅补跑失败/缺失用例
medeval rejudge <run目录>                             # 离线重判：冻结用例+留痕零 bot 调用重跑判分（默认对比源 run）
medeval prune --config config.yaml [--dry-run]       # 按 config.run.retention 清理历史胖产物（report.json 永久保留）
medeval verify-heuristics                            # 改 HardGate 前后必跑（见 §5）
pytest -m golden                                     # HardGate 黄金集回归

# 评测平台（Web）
pip install -e ".[server]"                           # 后端依赖
scripts/dev_platform.sh                              # 开发：后端 :8000 + 前端 :5173（/api 代理）
scripts/serve_platform.sh --port 8000                # 生产：构建前端后由 FastAPI 静态托管
```

更多参数（`--score-profile` / `--limit` / `--dry-run` / `--diff-against`）、`validate` / `list-cases` 子命令见 `README.md`「快速开始（CLI）」。版本对比优先级：`--diff-against`（CLI）> `reporter.diff_against`（config）> 默认自动对比上一次。平台环境变量（`MEDEVAL_*`、飞书 `FEISHU_*` / `SESSION_SECRET`）见 `.env.example` 与 `server/README.md`。

## 5. 关键约定与治理（开发规范 · 务必遵守）

1. **HardGate 启发式受治理**：修改 `medeval/judges/hard_gate.py` 前后必须跑 `medeval verify-heuristics`——三检串联：关键词表上方 5 行结构化注释（sourced/owners/last_reviewed/scope/rationale）、`tests/golden/` 回归、新 `fingerprint()` 登记进 `docs/heuristics-changelog.md`。任一失败即非零退出。
2. **失败标签表自动生成**：README 的 `AUTO-GENERATED:failure-tags` 区块由 `python -m medeval.docs.gen_failure_tags` 生成，勿手改；新增 `FailureTag`（改 `models.py`）后重跑。
3. **用例 schema 不随意扩展**：新增用例复用现有 `TestCase` 字段；`sample_id` 全局唯一，乳腺癌统一用 `bc_` 前缀（单一 benchmark，已无 `_core_safety` 通用底座）。
4. **语义裁决器四条不可破约束**：①只能 `FAIL→PASS`，绝不 `PASS→FAIL`；②绝不触碰 `hard_gate.*`；③红旗用例（`red_flag_triage != none`）规则失败时**不自动救回**，改置 `needs_human_review=true` 交人工；④**每题最多救回 1 条**，禁救处方/治愈类 must_not。prompt/provider/model/开关纳入判分 `fingerprint`；pattern 补 `note` 可提升裁决准确率。
5. **配置要点（`config.yaml`）**：`adapter.type` 必须显式指定（mock 已下线，支持 `openai_compat` / `http`）；复现性默认 `temperature: 0.0`、`run.repeat: 1`（基线可用 `--repeat 3`）；评测有意义的前提是把 `adapter.openai_compat.system_prompt` 换成产品真实 prompt；四模块评分口径在 `scoring`（`module_max` / `function_deduction` / `grade_thresholds`），会写进 `RunReport.config_snapshot` 供 diff 区分「表现变化」与「口径变更」。
6. **辅助治理脚本** 在 `scripts/`：`audit_multi_turn_coverage.py`、`check_heuristics_changelog.py`、`lint_hard_gate_comments.py`、`scan_failure_tags.py`、`compute_agreement.py`（人审 vs 自动一致性度量）、`aidp_proxy.py`（Graphify OpenAI→AIDP 本地桥接）。

## 6. OpenSpec 工作流 & 易踩的坑

- **OpenSpec**：能力规格在 `openspec/specs/<capability>/spec.md`；进行中变更在 `openspec/changes/<name>/`（proposal / design / specs / tasks），归档在 `openspec/changes/archive/`。常用 `openspec list`、`openspec status --change <name> --json`、`openspec validate --strict`。`.cursor/skills/` 与 `.cursor/commands/` 提供 propose / explore / apply / archive 命令。
- **OpenSpec 读取约定（省 token · 强制）**：
  - **MUST NOT** 通读 `openspec/changes/archive/`（禁止 `grep`/批量 `read` 整个 archive 树）。
  - 查**现行契约** → 只读 `openspec/specs/<相关 capability>/spec.md`（按任务定点 1～2 个 capability）。
  - 查**某次历史决策** → 只打开**那一个** archive 目录的 `proposal.md`（必要时再加 `tasks.md`；delta 全文用 `git log -p openspec/specs/...`）。
  - **架构 / 依赖** → 优先 `graphify query`（见 `.cursor/rules/graphify.mdc`），而不是翻大段 spec 或 `GRAPH_REPORT.md`。
  - 进行中变更 → 只读 `openspec/changes/<name>/` 下 `openspec instructions apply` 列出的 `contextFiles`。
  - `.cursorignore` 已排除 `openspec/changes/archive/` 与 `graphify-out/` 的索引；手动路径仍可访问。
- **文档语言约定**（`openspec/config.yaml`）：正文用简体中文；代码、命令、变量、路径、Markdown 标题关键字（Proposal/Tasks）保留英文；技术术语不翻译。
- **需求正文必须含 `MUST`/`SHALL`**：每条 `### Requirement` / `### 需求` 正文 MUST 至少出现一次 ASCII 关键字 `MUST`/`SHALL`——校验器只认英文词，纯中文「必须」会让 `openspec validate --strict` 与 `openspec archive` 报 `Requirement must contain SHALL or MUST keyword` 并 abort。scenario 正文不强制。
- **Git 版本管理**：本仓库已 `git init`，默认分支 `main`。`.gitignore` 已排除 `.env`、`outputs/`、`uploads/`、`*.db`、`.venv/`、`node_modules/` 等——提交前用 `git status` 自查。在 Cursor 中查看改动：左侧 **Source Control**（`Cmd/Ctrl+Shift+G`）或 `git diff`。
- 医学用例为非专业人员构造，**仅供框架测试**，上线前必须临床专家评审（见 README 免责声明）。
- `outputs/` 每次评测落独立目录、**不覆盖**、会持续累积。`config.run.retention` 会在每次 run 收尾**自动滚动清理历史 run 的胖产物**（`traces.jsonl.gz` / `transcripts.xlsx`），但 `report.json` 与含 `KEEP` 哨兵的 run 永久保留——即 run 目录本身仍会累积，必要时自行清理。

## 7. 设计上下文（Design Context）

前端/界面相关改动前，先读项目根的两份设计文件（`impeccable` skill 在做任何设计输出前也会先读它们）：

- **`PRODUCT.md`**（战略 · who/what/why）：register（本项目=`product`，内部评测平台）、目标用户、产品目的、品牌个性（数据驱动 · 高效克制 · 工具感专业）、反面参照（花哨营销 / 老旧医院系统 / 玩具化 / 炫技大屏）、5 条设计原则、无障碍口径。
- **`DESIGN.md`**（视觉 · how it looks）：色板 / 字体 / 组件 / 间距 / 圆角 token（Google Stitch 格式）。**权威实现** = `frontend/src/styles.css`（Ink & Whitespace `:root` + Dashboard `--runs-*`）+ `frontend/src/theme.ts`（`palette` 镜像）+ Ant Design。**门禁**自动校验 CSS↔JS token 镜像：`cd frontend && npm run check:standards`。
- **impeccable skill**：项目内装在 `.cursor/skills/impeccable/`（与其它 Cursor skill 同目录）。入口 `node .cursor/skills/impeccable/scripts/context.mjs`。
- **前端开发流程规范**：`.cursor/rules/frontend-workflow.mdc`（glob `frontend/**` 自动加载）。取数经 `hooks/` + `frontend/src/api/`；**收尾 MUST** `npm run verify`（`scripts/verify_frontend.sh`）。
- **服务端开发规范**：`.cursor/rules/server-backend.mdc`（glob `server/**` 自动加载）。Router → Service → ORM；列表分页、`detail_json` 列投影、异常与日志口径见该文件。

