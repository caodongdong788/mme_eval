# HardGate Heuristics CHANGELOG

> 本文档登记 ``medeval/judges/hard_gate.py`` 中关键词表 / 正则 / 短语
> 的所有变更。每次改动必须新增一段记录，并把
> ``HardGateJudge.fingerprint()`` 的新值写在 "Fingerprint" 字段中。
>
> 治理脚本 ``scripts/check_heuristics_changelog.py`` 会校验：若 ``hard_gate.py``
> 中受治理的关键词表（见 ``scripts/lint_hard_gate_comments.py::_TABLES``）发生变化，
> 但本文件在同一 PR 内未更新，则该脚本 fail。该脚本目前需手动运行（仓库尚未接入 CI）；
> 在接入 CI / pre-commit 前，请改动关键词表后手动跑一次再提交。
>
> 此外 ``tests/test_judge_fingerprint.py`` 在 pytest 中会因 ``HardGateJudge.fingerprint()``
> 漂移而 fail，作为强制人工 review 的兜底（这层是自动生效的）。
>
> 关联：[govern-hard-gate-heuristics 提案](../openspec/changes/archive/2026-05-27-govern-hard-gate-heuristics/proposal.md)
> ｜ [漂移保护测试](../tests/test_judge_fingerprint.py)
> ｜ [黄金集](../tests/golden/)

## [v1.1.0] - 2026-06-15

* **Fingerprint**: `3066f1a4689d`
* **Author**: framework-author
* **Reviewers**: TBD-clinician
* **Scope**: P1 隐式红旗用户题面路由 + 扩展肿瘤急症/_EMERGENCY_PATTERNS
* **Changes**:
  - 新增 ``_IMPLICIT_EMERGENCY_USER_PATTERNS``：用户题面含急症线索时升级分诊要求。
  - 扩展 ``_EMERGENCY_PATTERNS``：补充肿瘤急症相关短语（发热中性粒、脊髓压迫、高钙等）。
* **Golden Tests Impact**: 黄金集 13 条全绿，无新增/删除用例。

## [v1.0.0] - 2025-12-15

* **Fingerprint**: `98cb1591cde4`
* **Author**: framework-author
* **Reviewers**: TBD-clinician（占位，待上线前替换）
* **Scope**: 治理框架首次落地，关键词表内容沿用 P0 初始版本
* **Changes**:
  - 在 ``_EMERGENCY_PATTERNS`` / ``_REFERRAL_PATTERNS`` /
    ``_DOSAGE_PATTERN`` / ``_FREQ_PATTERN`` / ``_DIETARY_CONTEXT_WORDS`` /
    ``_DRUG_CONTEXT_WORDS`` / ``_DIAGNOSIS_PHRASES`` /
    ``_DISCLAIMER_PATTERNS`` 上方补齐 5 行结构化注释
    （sourced / owners / last_reviewed / scope / rationale）。
  - 关键词表的字面量内容**未变**，因此 fingerprint 保持 ``98cb1591cde4``。
* **Golden Tests Impact**: 黄金集首次落地共 11 条（6 pass + 5 fail），
  全部通过；后续扩充计划：每张表至少 3 条正例 + 2 条反例（目标 30+ 条）。
* **README Notice**: 把"修改 HardGate 前的本地自检"小节加入 README。

<!-- 新版本请在上方按倒序追加，模板：
## [vX.Y.Z] - YYYY-MM-DD
* **Fingerprint**: `xxxxxxxxxxxx`
* **Author**: <github-handle>
* **Reviewers**: <github-handle1>, <github-handle2>
* **Scope**: <one-line summary>
* **Changes**: <bullet list of pattern/regex/list diffs>
* **Golden Tests Impact**: <pass/fail count delta>
-->
