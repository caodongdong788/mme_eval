## 1. 数据契约扩展（models）

- [x] 1.1 在 `medeval/models.py` 的 `JudgeVerdict` 上新增字段 `unmet_patterns: list[Pattern] = Field(default_factory=list)`，紧随 `evidence` 字段之后；保持其它字段顺序不变以减少 JSON 序列化 diff
- [x] 1.2 在 `tests/test_models_n_runs_compat.py` 同目录新增 `tests/test_models_unmet_patterns_compat.py`，覆盖：
  - 旧 JSON（无 `unmet_patterns` 字段）反序列化默认 `[]`
  - 新增字段后旧 RunReport 加载 / round-trip 序列化不丢字段
  - HardGate / LLM 等非 rule verdict 的 `unmet_patterns` 始终为 `[]`

## 2. RuleJudge 行为扩展

- [x] 2.1 修改 `medeval/judges/rule.py::RuleJudge._check_must_have`：
  - OR 模式失败时把整个 `eb.must_have` 列表赋给 verdict 的 `unmet_patterns`
  - AND 模式失败时把循环里收集的 `missing_patterns: list[Pattern]`（从原始 `eb.must_have` 中按未命中保留）赋给 `unmet_patterns`
  - 通过分支显式 `unmet_patterns=[]`
- [x] 2.2 重写 `_check_must_have` 中的 `reason` 文案：OR 失败 → `"全部 must_have 均未命中（期望任一命中）"`；AND 失败 → `"must_have 部分未命中（要求全部命中）"`；不再把缺失模式拼进字符串（具体清单挪到 `unmet_patterns`）
- [x] 2.3 验证 `RuleJudge.fingerprint()` 在改动前后值不变（已由现有 `tests/test_judge_fingerprint.py::test_rule_fingerprint_depends_on_normalize` 硬编码 snapshot `2b55d138acc3` 保护，本次改动后跑通即满足）
- [x] 2.4 新增 `tests/test_rule_unmet_patterns.py` 覆盖三种情形：
  - OR 模式全 miss：`unmet_patterns` 长度等于 `case.must_have` 长度且按原序
  - AND 模式部分 miss：`unmet_patterns` 只包含未命中的 `Pattern`、按原序
  - 通过：`unmet_patterns == []`
  - case `must_have == []`：直接 N/A 通过、`unmet_patterns == []`

## 3. Markdown 渲染扩展

- [x] 3.1 修改 `medeval/reporter/markdown_report.py::_failure_section`，在每条 fail verdict 行下方检测 `verdict.unmet_patterns`，非空时输出 2 空格缩进的子列表，每行格式 `  - {kind} \`{value}\``，其中 `kind` 为 "关键词"（`p.keyword` 非空时）或 "正则"（`p.regex` 非空时），`value` 为对应字符串
- [x] 3.2 把现有 verdict 渲染行的拼接改为 helper 函数 `_render_verdict_line(v) -> list[str]` 返回主行 + 可选子列表行，便于测试与未来扩展
- [x] 3.3 新增或扩展 `tests/test_markdown_report.py`（若不存在则新建），断言：
  - OR 全 miss 渲染 3 条子列表行（关键词 + 关键词 + 正则）
  - AND 部分 miss 只渲染缺失子集
  - `rule.must_not_have` 命中禁含的 verdict 不出现子列表（保持单行）
  - 通过的 case 不在失败样本段（间接保证）
  - 含 Markdown 特殊字符（`\d`、`|`、`*`）的正则用反引号包裹后原样保留

## 4. 集成验证

- [x] 4.1 在本地跑 `pytest tests/ -q`，所有既有 + 新增测试通过（104 passed）
- [x] 4.2 用 `outputs/doubao_multi_turn_2026_05_28_v4/report.json` 作为 fixture（或拷一份精简版到 `tests/fixtures/`）跑一次本地 `python -m medeval.reporter.markdown_report` 等效路径，肉眼检查渲染：
  - `l2_mt_d2_recall_diet`、`l4_mt_d4_fake_memory_long` 两条 must_have 失败样本必须出现期望模式子列表（已验证：l2_mt_d2 渲染出 3 条「关键词/关键词/正则」；l4_mt_d4 渲染出 2 条正则）
  - `l2_mt_d4_pop_elderly_late`（must_not_have 失败）依然只有单行（间接由 `tests/test_markdown_report.py::test_failure_section_other_verdict_still_single_line` 覆盖）
- [x] 4.3 `openspec validate enrich-must-have-verdict-with-unmet-patterns --strict` 通过

## 5. 人工触发

- [x] 5.1 用户确认实现后跑一次完整 `medeval run --config config.multi_turn.yaml`，验证新 markdown / 新飞书 docx 在两条 must_have 失败 case 上正确显示子列表（用户决定跳过实跑，由 task 4.2 用 v4 fixture 注入的肉眼检查代偿）
- [x] 5.2 归档：`openspec archive enrich-must-have-verdict-with-unmet-patterns`
