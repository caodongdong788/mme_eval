## 1. 模型层：FailureTag 加 label_zh 元数据

- [x] 1.1 `medeval/models.py` `_TagMeta` dataclass 新增 `label_zh: str` 字段（无默认值，强制提供）
- [x] 1.2 `_TAG_META` dict 全部 15 个条目补充 `label_zh`：
  - 已 emit 8 条：`MISSED_RED_FLAG="漏报红旗"` / `UNDER_REFERRAL="转诊不足"` / `IMPROPER_PRESCRIPTION="越界处方"` / `OVER_DIAGNOSIS="越界确诊"` / `DISCLAIMER_MISS="缺免责"` / `INQUIRY_INCOMPLETE="问诊不足"` / `CONSTRAINT_VIOLATION="触发禁词"` / `ADAPTER_ERROR="调用失败"`
  - 预留 7 条：`EMPATHY_MISS="共情不足"` / `POPULATION_BLIND="人群盲区"` / `DIFFERENTIAL_NARROW="鉴别窄"` / `MEDICAL_HALLUCINATION="医学幻觉"` / `OVER_REFUSAL="过度拒答"` / `DIALOG_BREAK="上下文断"` / `TOOL_MISUSE="工具误用"`
- [x] 1.3 `FailureTag` 类新增 `label_zh` property，等价于 `_TAG_META[self].label_zh`（与现有 `dimension` / `description` property 风格一致）
- [x] 1.4 加启动期完整性 assert：`all(meta.label_zh for meta in _TAG_META.values())`，错误消息包含具体缺失的成员名

## 2. 渲染层：markdown_report 走中文短标签

- [x] 2.1 `medeval/reporter/markdown_report.py` 新增 `_tag_to_zh_label(tag_str: str) -> str` helper，内部 `try: FailureTag(tag_str).label_zh except ValueError: return tag_str`，并在 docstring 标注降级路径用于历史 report.json 兼容
- [x] 2.2 改造失败样本段（line 104 附近）：`**失败标签：** {', '.join(_tag_to_zh_label(t) for t in r.failure_tags) or '—'}`
- [x] 2.3 改造概览段「失败归因 Top 标签」表（line 160~165 附近）：表格行写成 `| {_tag_to_zh_label(tag)} | {cnt} |`（去掉反引号包裹，因为中文短词不需要 code 风格）
- [x] 2.4 grep 确认 `markdown_report.py` 中已不再有 `r.failure_tags` 直接拼接英文 enum value 的代码路径（只剩 helper 调用）

## 3. 数据层不动：Excel transcript 与 report.json 保持英文

- [x] 3.1 阅读 `medeval/reporter/excel_transcript.py`，确认 `failure_tags` 列写英文 enum value 的代码路径**保持不变**（不做改动，不引用 helper）
- [x] 3.2 阅读 `medeval/reporter/aggregator.py`，确认 `failure_tag_counter` 的 key 仍是英文 enum value（不做改动）

## 4. 文档同步：README 失败标签清单

- [x] 4.1 `medeval/docs/gen_failure_tags.py` 渲染逻辑改为表格 `| 短标签 | 英文 enum | 详细说明 |` 三列（dimension 已作为段标题，无需重复列）
- [x] 4.2 跑 `python -m medeval.docs.gen_failure_tags` 输出验证，再 `--write` 同步 README
- [x] 4.3 `gen_failure_tags --check` 通过：README 与 FailureTag 词表一致

## 5. 测试

- [x] 5.1 新建 `tests/test_failure_tag_label_zh.py`：覆盖词表严格一致 / 不重复 / 不撞 dimension / 长度区间 / 启动 assert 行为 / 已 emit 与预留全部覆盖
- [x] 5.2 修改 `tests/test_markdown_report.py`：加 8 个新 case 覆盖失败样本段中文渲染 / 概览表中文渲染 / 未知 tag 降级 / 空列表
- [x] 5.3 修改 `tests/test_excel_transcript.py`：加断言锁定 `failure_tags` 列保持英文 enum value，不允许中文短标签泄漏到 Excel
- [x] 5.4 跑 `pytest tests/ -q`，全绿（151 passed）
- [x] 5.5 跑 `openspec validate --strict localize-failure-tags-zh`，全绿

## 6. 端到端回归

- [x] 6.1 拿 v7 的 `outputs/doubao_multi_turn_2026_05_29_v7/report.json`，用新 `markdown_report.render_markdown()` 重新生成 markdown：失败归因 Top 标签表与 8 条失败样本「失败标签」行全部中文，零英文 enum value 残留
- [x] 6.2 跑完整 `medeval run --config config.multi_turn.yaml` 出 v8（87.5% 通过率 / N=3 stable_pass=31 flaky=6 stable_fail=3），落盘 markdown 与飞书 docx 均完全中文化（`触发禁词` / `越界处方` / `问诊不足` / `越界确诊`），飞书地址：https://bytedance.larkoffice.com/docx/FMgVdchLToEPn7xghQIlAGhVgOh
