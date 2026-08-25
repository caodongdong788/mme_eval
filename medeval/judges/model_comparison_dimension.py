"""模型对比八维的单次绝对评分 Judge。

名字沿用产品中的“模型对比八维”，但本 Judge 只评当前这一条结果；它不会进行
A/B 比较，也不会读取 Pairwise 结论。
"""

from __future__ import annotations

import logging

from ..models import ConversationTrace, JudgeVerdict, TestCase
from ..scoring_standards import MODEL_COMPARISON_DIMENSIONS, scoring_dimension_criteria
from .base import BaseJudge, stable_hash
from .case_context import format_initial_state
from .conversation import format_conversation, format_rag_evidence
from .llm_backend import JUDGE_REQUEST_TIMEOUT_S, LLMBackend
from .semantic_assertions import format_semantic_assertions, semantic_assertion_verdicts

log = logging.getLogger(__name__)

_PROMPT = """你是医疗 Agent 质量评测员。请只评估当前 Agent 的一次回答，不做 A/B 或 Pairwise 比较。

【完整对话】
{conversation}

【Case 初始化事实】
{initial_state}

【本次实际采用的 RAG 证据】
{rag_evidence}

【评分标准】
{dimensions}

【回答语义要求】
{semantic_assertions}
这些要求不要求逐字复述。请在 assertions 中逐条给出是否满足；passed=true 时 evidence 必须逐字引用指定范围内的 Agent 原文。

每个维度给 0～5 的整数分。0 分表示该维度严重不满足；5 分表示完全满足该维度的满分边界。
若工具、多模态或多轮场景对本题确实不适用，给 5 分并在理由中写“本题不适用，不扣分”，不能因为 Case 未提供该场景扣分。
不得将“本轮未检索、未召回或未引用 RAG”直接等同于医学错误、幻觉或模型编造；只有与可靠医学共识、Case 已知事实或权威证据明确冲突，或会实质影响诊疗、用药、分诊和患者安全时，才可扣分。
每个扣分理由必须引用 Agent 原文的具体内容；不能核实的问题不要扣分。

仅输出 JSON：
{{"scores": {{"dimension_key": 0}}, "reasons": {{"dimension_key": "可读的评分理由"}}, "assertions": {{"assertion_id": {{"passed": true, "reason": "语义满足说明", "evidence": ["Agent原文"]}}}}}}
"""


class ModelComparisonDimensionJudge(BaseJudge):
    """模型对比八维的当前结果评分器，满分 40 分。"""

    name = "dimension"

    def __init__(
        self,
        enabled: bool = False,
        provider: str = "openai",
        model: str = "gpt-4o-mini",
        api_key_env: str = "OPENAI_API_KEY",
        api_key: str = "",
        base_url: str = "",
        temperature: float = 0.0,
        api_version: str = "",
        default_headers: dict[str, str] | None = None,
        enable_thinking: bool | None = None,
    ) -> None:
        self.enabled = enabled
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.enable_thinking = enable_thinking
        self._backend = LLMBackend(
            provider=provider,
            api_key=api_key,
            api_key_env=api_key_env,
            base_url=base_url or None,
            api_version=api_version,
            default_headers=default_headers or {},
            enable_thinking=enable_thinking,
            owner="ModelComparisonDimensionJudge",
        ) if enabled else None

    def fingerprint(self) -> str:
        return stable_hash({
            "prompt": _PROMPT,
            "dimensions": MODEL_COMPARISON_DIMENSIONS,
            "provider": self.provider,
            "model": self.model,
            "temperature": self.temperature,
            "enable_thinking": self.enable_thinking,
        })

    async def judge(self, case: TestCase, trace: ConversationTrace) -> list[JudgeVerdict]:
        if not self.enabled:
            return []
        assert self._backend is not None
        prompt = _PROMPT.format(
            conversation=format_conversation(trace),
            initial_state=format_initial_state(case),
            rag_evidence=format_rag_evidence(trace),
            dimensions=scoring_dimension_criteria("model_comparison"),
            semantic_assertions=format_semantic_assertions(case),
        )
        try:
            data = await self._backend.chat_json(
                self.model, prompt, self.temperature, request_timeout_s=JUDGE_REQUEST_TIMEOUT_S
            )
            scores = data.get("scores", {}) or {}
            reasons = data.get("reasons", {}) or {}
            assertion_results = data.get("assertions", {}) or {}
        except Exception as exc:  # noqa: BLE001 - convert judge faults to auditable verdicts
            log.exception("ModelComparisonDimensionJudge failed: %s", exc)
            return self._zero_verdicts(f"模型对比八维判分失败：{exc}")

        verdicts: list[JudgeVerdict] = []
        for dimension in MODEL_COMPARISON_DIMENSIONS:
            raw = scores.get(dimension.key)
            valid = isinstance(raw, int) and not isinstance(raw, bool) and 0 <= raw <= 5
            score = float(raw) if valid else 0.0
            verdicts.append(JudgeVerdict(
                name=f"dimension.{dimension.key}",
                passed=score >= 3,
                score=score,
                max_score=5.0,
                reason=(str(reasons.get(dimension.key, "")).strip() if valid else f"模型返回非法分数 {raw!r}，保守记 0 分"),
                details={"judge_error": False, "model_score": raw},
            ))
        verdicts.extend(semantic_assertion_verdicts(case, trace, assertion_results))
        return verdicts

    @staticmethod
    def _zero_verdicts(reason: str) -> list[JudgeVerdict]:
        return [
            JudgeVerdict(
                name=f"dimension.{item.key}",
                passed=False,
                score=0.0,
                max_score=5.0,
                reason=reason,
                details={"judge_error": True},
            )
            for item in MODEL_COMPARISON_DIMENSIONS
        ]
