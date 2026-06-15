## Why

`config.yaml` 目前全程以**裸 dict** 流转：`_load_config` → `yaml.safe_load` → `dict`，再由 `cli._build_judges` / `_build_adjudicator` / `build_adapter` / `_check_thresholds` / `reporter.scoring` 各自 `.get(key, default)` 取值。后果：

- **拼错字段静默吞掉**：`self_consistensy`（漏字母）、`adaptor`（误拼 adapter）、`provdier` 等不会报错，只是默默用默认值 → 用户以为配了其实没生效。
- **默认值散落多处**：同一字段的默认值在多个 `.get(k, default)` 里各写一份，易漂移。
- **跨字段约束晚爆**：`provider: azure` 缺 `base_url/api_version` 要等到 client 构建时才炸；`adapter.type` 与子块不匹配也只在构造时发现。

研发阶段不考虑历史兼容，可直接引入类型化 schema 并在加载期 fail-fast。

## What Changes

- 新增 `medeval/config.py`：用 Pydantic v2 定义整棵配置的 `Config` 模型（`run/cases/adapter/judges/reporter/thresholds/scoring`），作为**配置层校验与跨字段约束的单一真值源**。
  - **分区 forbid**：结构化节点 `extra="forbid"`（抓拼错/多余字段）；自由键值叶子（`default_headers` / `extra_body` / `http.headers` / `module_max` / `grade_thresholds` / `gates` / `profiles` 的名字）保持 `dict` 宽松。
  - **跨字段校验**：`adapter.type` ↔ 对应子块存在；`provider ∈ {openai, azure}` 且 `azure` 必须有 `base_url + api_version`；`aggregate ∈ {median, min}`；`self_consistency ≥ 1`；`pass_rule` 形状（`"perfect"` 或 `{type: threshold, min_composite, gates}`）。
  - **友好报错**：`load_config` 捕获 `ValidationError`，渲染成定位到键路径的中文报错并非零退出，而非抛原始 traceback。
- `cli._load_config` 返回 `Config`；`run`/`validate`/`list-cases` 改吃 typed；`_build_judges(config.judges)` / `_build_adjudicator(...)` / `_check_thresholds(report, config.thresholds)` 接 typed；`build_adapter(config.adapter.type, config.adapter.model_dump())`（adapter 内部保持 dict 解析不变）。
- `RunReport.config_snapshot = config.model_dump(mode="json")`：序列化后等价 JSON，**reporter / diff / excel 零改动**。
- **scoring 不改 dict 接口**（关键风险规避）：`reporter/scoring.py` 的 `resolve_profile/score_case/apply_grading` 仍吃 dict——其实际输入来自 `config_snapshot["scoring"]`（已是 `model_dump` 产物，已校验、已定型）。数值默认（module_max/扣分步长/阈值）继续由 scoring 独占，`Config.ScoringCfg` 只校验结构与禁拼错、**不重复数值默认**，从根上消除双默认源。

## Capabilities

### Modified Capabilities
- `evaluation-cli`：新增"配置加载 MUST 经类型化 schema 校验、未知/拼错字段与跨字段非法在加载期 fail-fast"的要求；`config_snapshot` 由原始 dict 改为校验后模型的 `model_dump(mode="json")`（语义等价，diff 行为不变）。

## Impact

- 代码：新增 `medeval/config.py`；改 `medeval/cli.py`（load/build/thresholds 接 typed、snapshot=model_dump）；新增 `tests/test_config.py`。
- 行为：合法 `config.yaml` 行为不变；非法/拼错配置由"静默" → "加载即报错"（fail-fast，属改进）。判分结果零变化。
- 兼容性：研发阶段，放弃历史 report.json 兼容；`config_snapshot` 形状改为 model_dump（含默认填充），同 schema 两次 run 不产生伪 diff。
- 依赖：复用已有 `pydantic`（models.py 已用），不引入新依赖。
