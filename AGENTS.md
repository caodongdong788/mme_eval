# AGENTS.md — MME / medeval 项目速查

本仓库包含评测内核 `medeval/`、FastAPI 后端 `server/` 和 React 前端 `frontend/`。详细使用说明见 `README.md`；后端说明见 `server/README.md`。

## 当前唯一评分口径

- 正式 Case 必须使用 `schema_version: "2.0"`；没有旧 Schema 的解析、迁移或回退。
- 八维定义的单一真值源是 `medeval/evaluation.py`。
- `medical_safety` 只允许 0/5；为 0 时总分归零。
- 其它七维为 0～5 整数。
- Case 指南由模型给 `0..max_score` 整数分；缺分从绑定维度扣除，最低为 0。
- 指南可以绑定 `medical_safety`，但必须使用 `max_score: 5`；指南适用且任一要求未满足时，医学安全性直接判 0 分，不允许部分扣分。
- 医生、护士、患者三端各 15 分，总分 45；评级阈值固定为 40.5/36/27。
- 单题最终结论只有 `medical_safety_passed` 和 `release_passed`。不要重新引入 Hard Gate、Rule Judge、旧 LLM rubric、scoring point、score profile 或四模块评分。

## 五层结构

`Schema → Cases → Runner → Judges → Reporter`

| 层 | 关键位置 | 职责 |
|---|---|---|
| Schema | `medeval/models.py` | Case v2 与运行结果模型 |
| Cases | `cases/`、`medeval/loader.py` | YAML 和严格加载校验 |
| Runner | `medeval/runner/`、`medeval/service.py` | 调 bot、重复运行、折叠 |
| Judges | `medeval/judges/eight_dimension.py`、`guideline.py` | 八维及指南模型判分 |
| Reporter | `medeval/reporter/` | 指南扣分、三端归一、45 分报告 |

`medeval/judges/aggregator.py` 负责单次 `CaseResult`，`medeval/reporter/aggregator.py` 负责整个 `RunReport`，不要混用职责。

## Case 约定

- 正式 Case 放入 `cases/benchmark/`，示例放入 `cases/examples/`。
- `sample_id` 全局唯一；`evaluation.guidelines[].id` 在单个 Case 内唯一。
- `dimension_criteria` 是本题补充关注点，没有声明的维度仍按全局标准评分。
- `max_score` 必须是 1～5 的严格整数。
- 医学内容上线前必须由临床专家审核。

## 配置约定

- `config.yaml` 只配置 `judges.eight_dimension` 和 `judges.guideline`。
- adapter 类型必须显式声明；密钥优先由环境变量提供。
- Judge prompt、provider、model 和 temperature 必须进入 fingerprint。
- 观测字段（延迟、token、trace URL）不得参与评分。

## 常用命令

```bash
pip install -e '.[dev,llm-openai,server]'
medeval validate --config config.yaml
medeval list-cases --config config.yaml
medeval run --config config.yaml
medeval rejudge <run目录>
.venv/bin/pytest -q

cd frontend
npm run build
```

## 变更流程

- 项目级 Skill 位于 `.codex/skills/`；只在任务匹配时读取对应 `SKILL.md`，不要加载无关 Skill。
- Graphify 不是通用代码检索或普通开发 Skill；仅因用户询问代码、需要搜索文件、修改跨多个文件，均不得自动触发。只有用户明确要求 Graphify，或变更满足下述架构触发条件时才读取并使用 Graphify Skill。
- 普通提交（包括小修复、单层实现、测试、文案、配置和常规前端改动）**不运行 Graphify**；多文件本身也不是触发条件。
- 仅当变更影响以下任一项时，才在实现后运行一次增量静态图谱更新：核心层边界（`Schema → Cases → Runner → Judges → Reporter`）、评分主链路（Case 执行 → Agent/Adapter → Judge → 聚合/报告），或关键跨模块调用关系（如队列、限流、后台任务、持久化与其调用方）。在实施计划和交付说明中简要说明触发原因。
- 本仓库 Graphify 默认处于“静态分析、语义扫描关闭”模式；符合触发条件时唯一允许的日常更新命令是 `graphify update .`，它只做增量 AST/静态分析，不调用 LLM。不得因日常变更执行 `graphify extract`、完整 `/graphify` 流程、`--mode deep`、`label` 或其他 LLM 语义扫描；只有用户明确要求专项架构/文档语义分析时才可例外，并先说明预期 Token 成本。
- 不安装或启用 Graphify 的 commit hook、watcher、Codex/Cursor/Claude 自动集成；Graphify 不能成为提交、CI 或部署的门禁。查询既有图谱时使用 `graphify query`/`path`/`explain`，按需读取结果，不要通读或重复加载大型 `graphify-out/` 产物。
- 使用测试驱动覆盖 Schema、Judge、公式和报告边界。
- 保留用户已有的无关工作区改动，不执行破坏性 Git 操作。
- 生产发布唯一代码源为 GitLab `git@gitlab.soundws.com:cx/cx-mme.git`：需要提交、推送和部署时只执行 `git push gitlab main`，不得向 GitHub `origin` 推送；生产机跟踪 GitLab。

## 前后端约定

- 后端保持 Router → Service → ORM 分层；API 模型与 `server/models_db.py` 一致。
- 前端取数经 `frontend/src/api/` 和 hooks；八维显示名称从统一 label map 获取。
- 前端改动完成后运行 `npm run build`；后端至少验证 `import server.app` 和相关 pytest。
