# Tasks

## 裁决器：红旗也救回 + 默认开启
- [x] 移除 `semantic_adjudicator.adjudicate` 的红旗早退安全闸，红旗用例改为照常进入救回循环
- [x] 红旗用例仍设 `needs_human_review=True`，summary verdict 注明救回结果需人工确认
- [x] `config.yaml` 裁决器 `enabled` 默认改为 `true`
- [x] 更新 `tests/test_semantic_adjudicator.py`：红旗真违规维持失败+标记、红旗误杀被救回+标记

## 体验软分：默认锚点（方案 A）+ 逐维度归因
- [x] `llm.py` 新增 `_DEFAULT_DIMENSION_ANCHORS` 与 `_default_anchor_points`
- [x] `_format_rubric` 在无 `points` 时注入默认锚点，有 `points` 时以用例为准
- [x] `_PROMPT_TEMPLATE` 增加「严格对照评分标准逐档给分」指令
- [x] `LLMJudge.fingerprint()` 纳入锚点表；更新 `EXPECTED_FINGERPRINTS["llm_default"]`
- [x] `scoring.py` 体验失分按 `llm.*` 逐维度归因（维度名/得分/满分/理由）
- [x] 新增 `tests/test_weighted_grading.py` 逐维度归因用例

## 报告：救回留痕 + 固定栏 + xlsx 中间产物
- [x] `scoring.py` 对 `adjudicated=True` 的 `must_have`/`must_not_have` 追加「已救回」标注（不扣分）
- [x] `excel_transcript.py` `freeze_panes` 改到「评级」列下一列
- [x] `cli.py` 飞书发布成功后删除本地 `transcripts.xlsx`，关闭/失败时保留兜底
- [x] 更新 `tests/test_excel_transcript.py` 冻结列断言

## Spec 同步
- [x] `judging-pipeline`：红旗救回 + 默认开启 + LLM 默认锚点
- [x] `reporting`：transcripts 中间产物 + 固定栏 + 体验逐维度归因 + 救回标注
- [x] `openspec validate` strict 通过

## 验证
- [x] 全量 `pytest` 通过（203）
- [x] 全量 benchmark 跑通，误杀 case 被救回验证
