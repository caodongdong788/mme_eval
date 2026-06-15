## 1. 引入 FailureTag Enum 与元数据

- [x] 1.1 在 `medeval/models.py` 定义 `class FailureTag(str, Enum)`，包含两类成员：
  - **已 emit（8 个）**：`MISSED_RED_FLAG` / `UNDER_REFERRAL` / `IMPROPER_PRESCRIPTION` / `OVER_DIAGNOSIS` / `DISCLAIMER_MISS` / `INQUIRY_INCOMPLETE` / `CONSTRAINT_VIOLATION` / `ADAPTER_ERROR`
  - **预留 Enum 成员（暂无 Judge emit）**：`EMPATHY_MISS` / `POPULATION_BLIND` / `DIFFERENTIAL_NARROW` / `MEDICAL_HALLUCINATION` / `OVER_REFUSAL` / `DIALOG_BREAK` / `TOOL_MISUSE`
  - 在 `_TAG_META` 中为"预留成员"附加 `description` 末尾标注"_（暂未由 Judge emit，将由 llm-judge-emit-failure-tags 提案启用）_"
- [x] 1.2 定义 `_TagMeta` dataclass（dimension + description），按表格补齐每个标签的元数据
- [x] 1.3 暴露 `FailureTag.dimension` 和 `FailureTag.description` 便捷属性（通过类方法或 property）
- [x] 1.4 编写单测 `tests/test_failure_tags.py`：每个成员都有元数据；dimension 取值在白名单内

## 2. Judge emit 切换为 Enum

- [x] 2.1 `medeval/judges/hard_gate.py` 中所有 `failure_tags=["..."]` 改为 `failure_tags=[FailureTag.XXX]`
- [x] 2.2 `medeval/judges/rule.py` 中所有 `failure_tags=["..."]` 改为 Enum
- [x] 2.3 `medeval/judges/aggregator.py` 中 `tags.append("adapter_error")` 改为 `tags.append(FailureTag.ADAPTER_ERROR)`
- [x] 2.4 验证 `JudgeVerdict` / `CaseResult` 的序列化结果与之前的 JSON 字符串完全一致（snapshot 对比） — 在 5.3 集成验证中确认

## 3. 用例侧 failure_tags_candidates 强类型化

- [x] 3.1 写一次性扫描脚本 `scripts/scan_failure_tags.py`：遍历所有 cases YAML，输出每个非法 candidate 的位置与推荐映射
- [x] 3.2 根据 design.md 的迁移映射表批量修正 `cases/L4_adversarial/adversarial.yaml` 的 `prompt_injection_success` / `safety_violation` / `privacy_violation`
- [x] 3.3 批量修正 `cases/L3_red_flags/red_flags.yaml` 与 `cases/L2_scenarios/**` 中含 `population_blind` / `empathy_miss` 的用例 — 实际无需修正：这两个标签已作为预留 Enum 成员存在，用例 candidate 校验直接通过
- [x] 3.4 把 `TestCase.failure_tags_candidates` 类型由 `list[str]` 改为 `list[FailureTag]`
- [x] 3.5 `medeval validate` 必须能在新校验下通过；写单测覆盖"非法 candidate 必须抛 ValidationError"（见 tests/test_failure_tags.py::test_testcase_rejects_unknown_candidate）

## 4. README 自动生成对接

- [x] 4.1 新增 `medeval/docs/gen_failure_tags.py`，按 dimension 分组渲染 Markdown 表格
- [x] 4.2 在 README.md 中把当前"失败归因标签"段落替换为 `<!-- AUTO-GENERATED:failure-tags-start -->` / `<!-- AUTO-GENERATED:failure-tags-end -->` 包裹的占位
- [x] 4.3 写一个简短的 CI 检查脚本（pytest 或 make 命令）：运行生成器后 git diff 必须为空，否则失败（见 tests/test_failure_tags.py::test_readme_in_sync_with_enum）
- [x] 4.4 第一次运行生成器，提交结果到 README

## 5. 集成验证

- [x] 5.1 `pytest -q` 全部通过（13 passed）
- [x] 5.2 `medeval validate` 通过（99 条用例）
- [x] 5.3 `medeval run --adapter mock` 跑通且生成的 report.json 中 failure_tags 内容与之前等价（仍是 `list[str]`，值 `inquiry_incomplete` 等保持不变）
- [x] 5.4 `openspec-cn validate --all --strict` 通过
