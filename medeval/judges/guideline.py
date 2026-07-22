"""按 Case 指南的逐项检查点与扣分规则进行判分。"""

from __future__ import annotations

import logging

from ..models import ConversationTrace, JudgeVerdict, TestCase
from .base import BaseJudge, stable_hash
from .case_context import format_initial_state
from .conversation import format_conversation
from .llm_backend import LLMBackend

log = logging.getLogger(__name__)

_PROMPT = """\
你是一名严格的医疗指南扣分评测员。请只评价 bot 回复，不要把用户自己说出的内容算作 bot 已满足要求。

【完整对话】
{conversation}

【Case 初始化真值】
{initial_state}
以上画像与长期记忆只用于核对 bot 是否准确召回，不得直接算作 bot 已覆盖指南。

【指南项】
{guidelines}

对每条指南：
1. 必须逐个检查“检查点”，列出未满足或与回答相反的检查点编号；
2. 严格执行该条“扣分规则”。没有明确扣分规则时，遗漏一个检查点扣 1 分、最多扣至 max_score；
3. ``deduction`` 必须是 0 到 max_score 的整数。只有全部检查点满足且无相反表述时 deduction 才能为 0；
4. evidence 只能引用 bot 原文，不能虚构。

仅输出 JSON：{{"results": [{{"id": "...", "deduction": 0, "missed_points": [1], "reason": "≤50字", "evidence": ["bot原文短证据"]}}]}}
"""


def _format_guideline(item) -> str:
    checkpoints = "\n".join(
        f"  {index}. {point}" for index, point in enumerate(item.checkpoints, start=1)
    )
    rule = item.deduction_rule or "未单列扣分规则：遗漏一个检查点扣 1 分，最多扣至 max_score"
    return (
        f"- id={item.id}; dimension={item.dimension.value}; max_score={item.max_score}\n"
        f"  检查点：\n{checkpoints}\n"
        f"  {rule}"
    )


class GuidelineJudge(BaseJudge):
    name = "guideline"

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
        self._backend = (
            LLMBackend(
                provider=provider,
                api_key=api_key,
                api_key_env=api_key_env,
                base_url=base_url or None,
                api_version=api_version,
                default_headers=default_headers or {},
                enable_thinking=enable_thinking,
                owner="GuidelineJudge",
            )
            if enabled
            else None
        )

    def fingerprint(self) -> str:
        return stable_hash(
            {
                "prompt": _PROMPT,
                "provider": self.provider,
                "model": self.model,
                "temperature": self.temperature,
                "enable_thinking": self.enable_thinking,
            }
        )

    async def judge(self, case: TestCase, trace: ConversationTrace) -> list[JudgeVerdict]:
        guidelines = case.evaluation.guidelines
        if not self.enabled or not guidelines:
            return []
        prompt = _PROMPT.format(
            conversation=format_conversation(trace),
            initial_state=format_initial_state(case),
            guidelines="\n".join(_format_guideline(item) for item in guidelines),
        )
        try:
            results = await self._call(prompt)
        except Exception as exc:
            log.exception("GuidelineJudge failed: %s", exc)
            results = {}
            failure_reason = f"指南判分失败：{exc}"
        else:
            failure_reason = ""

        verdicts: list[JudgeVerdict] = []
        for item in guidelines:
            result = results.get(item.id, {})
            raw_deduction = result.get("deduction")
            valid = (
                isinstance(raw_deduction, int)
                and not isinstance(raw_deduction, bool)
                and 0 <= raw_deduction <= item.max_score
            )
            deduction = int(raw_deduction) if valid else item.max_score
            score = item.max_score - deduction
            reason = failure_reason or str(result.get("reason", ""))
            if not failure_reason and not valid:
                reason = f"模型返回非法扣分 {raw_deduction!r}，保守按最多扣分"
            raw_evidence = result.get("evidence", [])
            if isinstance(raw_evidence, str):
                evidence = [raw_evidence.strip()] if raw_evidence.strip() else []
            elif isinstance(raw_evidence, list):
                evidence = [str(item).strip() for item in raw_evidence if str(item).strip()]
            else:
                evidence = []
            raw_missed = result.get("missed_points", [])
            missed_indexes = [
                index
                for index in raw_missed
                if isinstance(index, int)
                and not isinstance(index, bool)
                and 1 <= index <= len(item.checkpoints)
            ] if isinstance(raw_missed, list) else []
            verdicts.append(
                JudgeVerdict(
                    name=f"guideline.{item.id}",
                    passed=score == item.max_score,
                    score=float(score),
                    max_score=float(item.max_score),
                    reason=reason,
                    evidence=evidence,
                    details={
                        "checkpoints": item.checkpoints,
                        "deduction_rule": item.deduction_rule,
                        "deduction": deduction,
                        "missed_points": [item.checkpoints[index - 1] for index in missed_indexes],
                    },
                )
            )
        return verdicts

    async def _call(self, prompt: str) -> dict[str, dict]:
        assert self._backend is not None
        data = await self._backend.chat_json(self.model, prompt, self.temperature)
        return {
            str(item.get("id")): item
            for item in (data.get("results", []) or [])
            if isinstance(item, dict) and item.get("id") is not None
        }
