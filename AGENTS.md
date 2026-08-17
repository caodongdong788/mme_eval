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
- 多文件或评分主链路变更应先更新 `graphify-out/`，写明实施计划，并在实现后严格校验。
- 使用测试驱动覆盖 Schema、Judge、公式和报告边界。
- 保留用户已有的无关工作区改动，不执行破坏性 Git 操作。
- 生产发布唯一代码源为 GitLab `git@gitlab.soundws.com:cx/cx-mme.git`：需要提交、推送和部署时只执行 `git push gitlab main`，不得向 GitHub `origin` 推送；生产机跟踪 GitLab。

## 前后端约定

- 后端保持 Router → Service → ORM 分层；API 模型与 `server/models_db.py` 一致。
- 前端取数经 `frontend/src/api/` 和 hooks；八维显示名称从统一 label map 获取。
- 前端改动完成后运行 `npm run build`；后端至少验证 `import server.app` 和相关 pytest。
