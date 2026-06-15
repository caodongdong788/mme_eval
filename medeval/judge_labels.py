"""Judge verdict 与 fingerprint 中文标签 —— 全栈单一信任源。

- ``judge_verdict_label`` / ``judge_verdict_label_map``：逐 verdict 名（如 ``hard_gate.red_flag``）
- ``FINGERPRINT_LABELS``：``RunReport.judge_fingerprints`` 的 key（如 ``hard_gate``）
"""

from __future__ import annotations

# judge_fingerprints key → 展示（供 run diff / compare 使用，保留历史英文后缀）
FINGERPRINT_LABELS: dict[str, str] = {
    "hard_gate": "硬门槛 HardGate",
    "rule": "规则 Rule",
    "llm": "LLM 评委",
    "scoring_point": "得分点 ScoringPoint",
    "semantic_adjudicator": "语义裁决 Adjudicator",
}

VERDICT_PREFIX_LABELS: dict[str, str] = {
    "hard_gate": "硬门槛",
    "rule": "规则",
    "llm": "体验",
    "scoring_point": "得分点",
    "semantic_adjudicator": "语义裁决",
}

VERDICT_SUFFIX_LABELS: dict[str, str] = {
    "red_flag": "红旗分诊",
    "no_prescription": "处方边界",
    "disclaimer": "免责声明",
    "must_have": "必含要点",
    "must_not_have": "禁含要点",
    "empathy": "共情",
    "clarity": "清晰度",
    "actionability": "可执行性",
    "safety": "安全",
    "professionalism": "专业度",
    "boundary": "边界感",
    "factual_accuracy": "事实准确性",
    "completeness": "完整性",
    "relevance": "相关性",
    "tone": "语气",
    # 用例库已出现、原前端 caseJudging.ts 未覆盖的 rubric 维度
    "triage_quality": "分诊建议",
    "multi_turn_consistency": "多轮一致性",
    "differential_thinking": "鉴别思维",
    "inquiry_completeness": "问诊完整性",
    "summary": "汇总",
}


def judge_verdict_label(name: str | None) -> str:
    """verdict 全名 → 中文标签；未知回退原名（与前端 fallback 一致）。"""
    if not name:
        return "-"
    idx = name.find(".")
    if idx < 0:
        return VERDICT_PREFIX_LABELS.get(name, name)
    prefix = name[:idx]
    suffix = name[idx + 1 :]
    pl = VERDICT_PREFIX_LABELS.get(prefix)
    sl = VERDICT_SUFFIX_LABELS.get(suffix)
    if pl and sl:
        return f"{pl}·{sl}"
    if pl:
        return f"{pl}·{suffix}"
    return name


def judge_verdict_label_map() -> dict[str, str]:
    """预置 verdict 名 → 标签表，供 API 与前端缓存。"""
    out: dict[str, str] = {}
    for prefix in VERDICT_PREFIX_LABELS:
        out[prefix] = judge_verdict_label(prefix)
        for suffix in VERDICT_SUFFIX_LABELS:
            key = f"{prefix}.{suffix}"
            out[key] = judge_verdict_label(key)
    return out
