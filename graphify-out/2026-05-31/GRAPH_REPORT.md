# Graph Report - .  (2026-05-31)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 918 nodes · 2704 edges · 40 communities (33 shown, 7 thin omitted)
- Extraction: 76% EXTRACTED · 24% INFERRED · 0% AMBIGUOUS · INFERRED: 642 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]

## God Nodes (most connected - your core abstractions)
1. `TestCase` - 109 edges
2. `ConversationTrace` - 91 edges
3. `Turn` - 75 edges
4. `ChatMessage` - 75 edges
5. `CaseResult` - 68 edges
6. `BaseJudge` - 63 edges
7. `Pattern` - 53 edges
8. `Level` - 52 edges
9. `JudgeVerdict` - 51 edges
10. `RunReport` - 50 edges

## Surprising Connections (you probably didn't know these)
- `HardGateJudge` --implements--> `JudgeVerdict`  [INFERRED]
  openspec/specs/judging-pipeline/spec.md → medeval/models.py
- `LLMJudge` --implements--> `JudgeVerdict`  [INFERRED]
  openspec/specs/judging-pipeline/spec.md → medeval/models.py
- `RuleJudge` --implements--> `JudgeVerdict`  [INFERRED]
  openspec/specs/judging-pipeline/spec.md → medeval/models.py
- `Change: add semantic rule adjudicator` --references--> `CaseResult`  [EXTRACTED]
  openspec/changes/archive/2026-05-29-add-semantic-rule-adjudicator/design.md → medeval/models.py
- `Change: localize failure tags to Chinese` --references--> `FailureTag`  [EXTRACTED]
  openspec/changes/archive/2026-05-29-localize-failure-tags-zh/design.md → medeval/models.py

## Import Cycles
- 1-file cycle: `medeval/reporter/aggregator.py -> medeval/reporter/aggregator.py`
- 2-file cycle: `medeval/models.py -> medeval/reporter/aggregator.py -> medeval/models.py`
- 3-file cycle: `medeval/models.py -> medeval/reporter/aggregator.py -> medeval/reporter/scoring.py -> medeval/models.py`

## Communities (40 total, 7 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.09
Nodes (90): BaseModel, Any, bool, str, CaseResult, ChatMessage, ConversationTrace, Level (+82 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (74): BaseAdapter, ChatRequest, ChatResponse, Adapter 抽象基类。  医疗 chatbot 评测对接口的要求：   * 支持多轮对话（必须能传完整 history）   * 支持 session_id, Adapter 必须是异步的，便于 Runner 做高并发。, _get_by_path(), HttpAdapter, _interpolate_env() (+66 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (73): Change: enrich must-have verdict with unmet_patterns, JudgeVerdict, Markdown reporter, CaseResult, int, JudgeVerdict, Path, Pattern (+65 more)

### Community 3 - "Community 3"
Cohesion: 0.11
Nodes (52): RuleJudge, SemanticRuleAdjudicator, ExpectedBehavior, HardGates, Pattern, 规则判分的必含 / 禁含集合。逻辑均为 OR（任一命中算命中）。, SemanticRuleAdjudicator, _judge_must_have() (+44 more)

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (49): datetime, Any, bool, CaseResult, float, int, RunReport, str (+41 more)

### Community 5 - "Community 5"
Cohesion: 0.11
Nodes (42): compute_guideline_match_rate(), _format_points(), _normalize_score(), ScoringPointJudge —— HealthBench 式专家得分点逐点打分。  设计：   * 仅对声明了 ``case.scoring_point, 覆盖 prompt 模板 + provider + model + temperature + enabled。          不覆盖 case 的得分点内, 归一化得分（含负分语义与 max_positive==0 边界）。      * max_positive > 0 → clip(achieved / max_, 从带 guideline 锚点的得分点派生指南匹配率（按点计数）。      命中 = 该点达到"期望状态"（正分点被满足 / 负分点未出现），即 per-po, ScoringPointJudge (+34 more)

### Community 6 - "Community 6"
Cohesion: 0.08
Nodes (34): GoldenCase, GoldenExpected, load_golden(), 黄金集 YAML 的 Pydantic schema。  YAML 顶层是 list，每条 item 形如::      - id: gold_001, GoldenCase, _any_match(), HardGateJudge, _has_word_in_window() (+26 more)

### Community 7 - "Community 7"
Cohesion: 0.12
Nodes (17): _pattern_intent(), _pattern_key(), SemanticRuleAdjudicator 不作为标准 judge 调用，逻辑在 ``adjudicate``。, 纳入 prompt 模板 + provider + model + 开关 + 快筛配置；         排除 api_key / base_url / api, 命中片段邻近窗口出现否定/条件线索 → 疑似误报的强信号。          纯确定性：只查命中位置前 ``window`` 个字符内是否含任一线索词。, 只读救回：仅在 rule.* FAIL 上介入，红旗走人工，其余尝试语义救回。, 禁含误杀：所有命中的禁词都判为"非主张"才救回；任一真违规则维持 FAIL。, 必含漏判：OR 语义任一满足即救回；AND 语义需全部满足。 (+9 more)

### Community 8 - "Community 8"
Cohesion: 0.14
Nodes (27): Change: add semantic rule adjudicator, SemanticRuleAdjudicator, Change: add weighted scoring and grading, Change: harden evaluation determinism (N-runs, temperature 0.0), medeval CLI, Excel transcript reporter, Reporting subsystem, apply_grading (weighted scoring and grading) (+19 more)

### Community 9 - "Community 9"
Cohesion: 0.08
Nodes (23): cases/breast_cancer/L1_knowledge/bc_basics.yaml, cases/breast_cancer/L2_scenarios/followup.yaml, cases/breast_cancer/L2_scenarios/genetic_special.yaml, cases/breast_cancer/L2_scenarios/pathology.yaml, cases/breast_cancer/L2_scenarios/psych_survivorship.yaml, cases/breast_cancer/L2_scenarios/screening.yaml, cases/breast_cancer/L2_scenarios/treatment.yaml, cases/breast_cancer/L3_red_flags/bc_oncology_emergencies.yaml (+15 more)

### Community 10 - "Community 10"
Cohesion: 0.13
Nodes (25): bool, CaseResult, float, int, str, _deduction_text(), _display_lines(), _fmt_points() (+17 more)

### Community 11 - "Community 11"
Cohesion: 0.19
Nodes (22): bool, CaseResult, _classify_stability(), fold_n_runs(), _is_majority_pass(), N-runs majority voting aggregator.  参见 OpenSpec change ``harden-evaluation-deter, 把每条 case 的 N 次 ``CaseResult`` 折叠为单个最终 ``CaseResult``。      输入：``list[list[CaseRe, _make_case() (+14 more)

### Community 12 - "Community 12"
Cohesion: 0.14
Nodes (21): Path, str, 把 transcripts.xlsx 上传为飞书 Sheet 文档。  参见 OpenSpec change ``add-transcript-excel-ou, 把本地 xlsx 上传为飞书 Sheet 文档；失败返回 None（不抛异常）。, 尝试 ``lark-cli drive +import``。      lark-cli 的 drive 子命令在新近版本中支持把本地文件导入为飞书在线文档/表, _try_import_via_drive(), publish_xlsx_to_lark Function, transcripts.xlsx Artifact (+13 more)

### Community 13 - "Community 13"
Cohesion: 0.09
Nodes (21): FailureTag, str, FailureTag.label_zh 元数据测试。  参见 OpenSpec change ``localize-failure-tags-zh``。  覆盖, 如果某成员 label_zh 被改成空串，import 期 assert 必须抛 AssertionError。      用 import_module 在隔, 直接补丁 _TAG_META 后重新跑 assert 逻辑，验证消息含成员名。, 预留标签也必须立即有 label_zh，不等到 LLM Judge 接入再补。, 枚举 / 期望词表 / _TAG_META 三方完全同步。, label_zh property MUST 等价于 _TAG_META[self].label_zh。 (+13 more)

### Community 14 - "Community 14"
Cohesion: 0.15
Nodes (18): _build_adjudicator(), _build_judges(), _check_thresholds(), list_cases(), _load_config(), main(), _print_judge_fingerprints(), _print_summary() (+10 more)

### Community 15 - "Community 15"
Cohesion: 0.22
Nodes (18): judge_all(), Aggregator —— 跑全部 judge 并聚合成 CaseResult。, fingerprint 提取出错不应阻塞评测；返回空字符串并打 trace 即可。, 从 verdict 列表派生 (hard_gate_passed, overall_passed, soft, soft_max, tags)。      单一, 在 verdict 被原地修改后（如语义裁决 FAIL→PASS）重算 CaseResult 的汇总字段。      只动 hard_gate_passed /, recompute_result_summary(), _run_judge(), _safe_fingerprint() (+10 more)

### Community 16 - "Community 16"
Cohesion: 0.14
Nodes (15): BaseJudge, LLMJudge, bool, float, Judge fingerprint 漂移保护测试。  任何关键词表 / prompt / 正则字面量的改动都会改变以下硬编码的 fingerprint， 触发此, 切换 api_key_env / base_url 不应改变判分逻辑 fingerprint., stable_hash 必须对相同 dict 给出相同结果，与键序无关。, 中文不会被 escape，hash 应稳定。 (+7 more)

### Community 17 - "Community 17"
Cohesion: 0.12
Nodes (16): FailureTag 词表自检 —— 强制每个成员都有元数据，并验证 Pydantic 校验。, README 与用例已引用的 7 个预留标签必须存在。, README 失败归因标签段必须与 FailureTag 词表同步（CI 防漂移）。, 每个 FailureTag 成员必须在 _TAG_META 中有完整元数据。, FailureTag.X.dimension / .description 必须可访问。, FailureTag 作为 str 子类，与字符串比较和 json 序列化必须等价。, 已 emit 的 8 个标签必须都存在（防回退）。, test_emit_categories_present() (+8 more)

### Community 18 - "Community 18"
Cohesion: 0.16
Nodes (14): _iter_yaml_files(), load_cases(), Path, str, TestCase, 用例加载器 —— 从 cases/ 目录读取 YAML 并做 Pydantic 校验。, 加载用例。      Args:         include: 包含的目录或文件路径（相对 base_dir）。         exclude: 排除的目, classify() (+6 more)

### Community 19 - "Community 19"
Cohesion: 0.22
Nodes (9): ABC, 对任意 JSON 可序列化对象计算稳定哈希 (sha1 前 12 位).      跨平台 / 跨 Python 版本稳定：       * sort_keys, stable_hash(), 硬门槛 Judge —— 医疗场景的三道生死线。  1. red_flag_triage —— 红旗症状是否触发正确的分诊建议      * required_, Judges 包：判分模块。  判分流程：   1. HardGate（硬门槛）—— 任一 fail 整题 fail，且不再叠加软分   2. Rule（必含/, LLM-as-Judge —— 对 rubric 软指标进行 0~max 打分。  设计：   * 只在 rubric 非空时调用。   * 输出严格 JSON, Rule Judge —— 用例侧声明的 must_have / must_not_have 校验。  * must_have：默认 OR（任一命中即通过）；若, SemanticRuleAdjudicator —— 规则失败路径上的"只读、只救回"兜底层。  参见 OpenSpec change ``add-semant (+1 more)

### Community 20 - "Community 20"
Cohesion: 0.24
Nodes (9): _match(), _normalize(), 覆盖归一化函数源码 + 实例配置 normalize 开关., bool, ConversationTrace, JudgeVerdict, Pattern, str (+1 more)

### Community 21 - "Community 21"
Cohesion: 0.20
Nodes (11): Enum, Difficulty, Population, 核心数据模型 —— 全部用 Pydantic 校验，保证 YAML 用例的结构正确。  设计原则：   * `TestCase` 是评测的最小单元，**所有运行, 软指标评分维度。值为各维度最大分。LLM Judge 据此输出 0~max 的分数。, 4~8 字短中文标签（markdown 报告 / README 渲染用）。          与 ``description`` 区别：``descriptio, Rubric, RubricItem (+3 more)

### Community 22 - "Community 22"
Cohesion: 0.19
Nodes (10): _enumerate_rubric(), _format_rubric(), 覆盖 prompt 模板 + 模型族 + 温度 + 双判分模式.          api_key / api_key_env / base_url / api, ConversationTrace, int, JudgeVerdict, str, TestCase (+2 more)

### Community 23 - "Community 23"
Cohesion: 0.21
Nodes (10): Path, RunReport, Path, str, JSON 形式的全量报告 —— 用于版本 diff 与人审界面。, write_json(), publish_report_file(), publish_to_lark() (+2 more)

### Community 24 - "Community 24"
Cohesion: 0.27
Nodes (12): _fingerprint_warning(), 对比两份 report 的 judge_fingerprints。      返回值：       - 完全一致 → ""       - 不一致 → 带 ⚠️, _minimal_report(), Path, str, diff_runs 的 fingerprint 警告路径。, 构造一份最小可 diff 的 report dict。, test_diff_runs_inserts_warning_at_top() (+4 more)

### Community 25 - "Community 25"
Cohesion: 0.20
Nodes (7): 一个 judge 可以返回多个 verdict（例如硬门槛分别返回三个）。, 返回该 Judge 实例的稳定 12 位哈希。          必须覆盖所有"会影响判分输出"的静态属性（patterns / prompt /, 所有 assistant 回复拼起来，便于跨轮匹配。, ConversationTrace, JudgeVerdict, str, TestCase

### Community 26 - "Community 26"
Cohesion: 0.24
Nodes (10): Change: localize failure tags to Chinese, FailureTag, 系统中所有失败归因标签的受控词表。      * Judge emit 时必须传 ``FailureTag`` 成员（不允许裸字符串）。     * 用例 YA, main(), int, Path, str, 扫描所有 cases YAML，列出 `failure_tags_candidates` 中不在 FailureTag 词表内的取值。  用法：     pyt (+2 more)

### Community 27 - "Community 27"
Cohesion: 0.20
Nodes (11): gold_fail_disclaimer_miss, gold_fail_improper_prescription_dosage, gold_fail_missed_red_flag_chest_pain, gold_fail_over_diagnosis, gold_fail_under_referral, gold_pass_dietary_salt, gold_pass_dietary_water_intake, gold_pass_differential_phrasing (+3 more)

### Community 28 - "Community 28"
Cohesion: 0.36
Nodes (9): _format_conversation(), 把完整对话渲染成 LLM Judge prompt 友好的中文标签格式。      规则：       * 仅 ``role=user`` 出现时 turn 编, LLMJudge prompt 多轮渲染单测。  确保 ``_PROMPT_TEMPLATE`` 与 ``_format_conversation`` 满足 `, test_five_turn_conversation_ordering(), test_single_turn_backward_compat(), test_system_turn_rendered_separately_and_excluded_from_index(), test_three_turn_conversation_increments_turn_index(), test_two_turn_conversation_renders_in_order() (+1 more)

### Community 29 - "Community 29"
Cohesion: 0.33
Nodes (9): Path, str, diff_runs(), _load(), _mock_baseline_warning(), _n_runs_warning(), 与上版本评测结果做 diff，输出 Markdown 片段。  输入是两份 JSON 报告路径，输出一段 Markdown：   * 总体通过率变化   * 新, 两份 report 的 n_runs 不一致时给提示。 (+1 more)

### Community 30 - "Community 30"
Cohesion: 0.47
Nodes (8): check(), main(), patch_readme(), 把 FailureTag 词表渲染为 Markdown，用于 README 的 AUTO-GENERATED 段。  用法：     python -m med, render(), int, Path, str

### Community 31 - "Community 31"
Cohesion: 0.29
Nodes (4): int, BaseHTTPRequestHandler, Handler, Minimal localhost proxy: OpenAI-style /v1/chat/completions -> ByteDance AIDP (Az

### Community 32 - "Community 32"
Cohesion: 0.38
Nodes (6): lint(), main(), int, Path, str, Lint `medeval/judges/hard_gate.py` 内每张关键词/正则表上方必须有 5 行结构化注释。  要求的 5 个字段（按任意顺序均可，

## Knowledge Gaps
- **61 isolated node(s):** `int`, `_TagMeta`, `TagDimension`, `int`, `Path` (+56 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TestCase` connect `Community 0` to `Community 1`, `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 6`, `Community 11`, `Community 14`, `Community 15`, `Community 17`, `Community 18`, `Community 19`, `Community 21`?**
  _High betweenness centrality (0.132) - this node is a cross-community bridge._
- **Why does `BaseJudge` connect `Community 15` to `Community 3`, `Community 5`, `Community 6`, `Community 7`, `Community 16`, `Community 19`, `Community 20`, `Community 22`, `Community 25`?**
  _High betweenness centrality (0.098) - this node is a cross-community bridge._
- **Why does `FailureTag` connect `Community 26` to `Community 2`, `Community 13`, `Community 15`, `Community 17`, `Community 19`, `Community 21`, `Community 30`?**
  _High betweenness centrality (0.091) - this node is a cross-community bridge._
- **Are the 65 inferred relationships involving `TestCase` (e.g. with `GoldenCase` and `Any`) actually correct?**
  _`TestCase` has 65 INFERRED edges - model-reasoned connections that need verification._
- **Are the 51 inferred relationships involving `ConversationTrace` (e.g. with `GoldenCase` and `ScoringPointJudge`) actually correct?**
  _`ConversationTrace` has 51 INFERRED edges - model-reasoned connections that need verification._
- **Are the 49 inferred relationships involving `Turn` (e.g. with `GoldenCase` and `bool`) actually correct?**
  _`Turn` has 49 INFERRED edges - model-reasoned connections that need verification._
- **Are the 47 inferred relationships involving `ChatMessage` (e.g. with `GoldenCase` and `ScoringPointJudge`) actually correct?**
  _`ChatMessage` has 47 INFERRED edges - model-reasoned connections that need verification._