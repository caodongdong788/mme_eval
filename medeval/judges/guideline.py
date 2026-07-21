"""对 Case 指南逐项给 0..max_score 部分分。"""

from __future__ import annotations

import logging

from ..models import ConversationTrace, JudgeVerdict, TestCase
from .base import BaseJudge, stable_hash
from .case_context import format_initial_state
from .conversation import format_conversation
from .llm_backend import LLMBackend

log = logging.getLogger(__name__)

_PROMPT = """\
你是一名严格的医疗指南覆盖度评测员。请只评价 bot 回复对每条指南要求的覆盖程度，不要把用户自己说出的内容算作 bot 的得分。

【完整对话】
{conversation}

【Case 初始化真值】
{initial_state}
以上画像与长期记忆只用于核对 bot 是否准确召回，不得直接算作 bot 已覆盖指南。

【指南项】
{guidelines}

每项只能给 0 到该项 max_score 的整数：满分=完整明确覆盖；约 2/3=覆盖主要内容；约 1/3=仅少量覆盖；0=未覆盖或相反。
仅输出 JSON：{{"results": [{{"id": "...", "score": 0, "reason": "≤50字", "evidence": "bot原文短证据"}}]}}
"""


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
            guidelines="\n".join(
                f"- id={item.id}; max_score={item.max_score}; criterion={item.criterion}; source={item.source}"
                for item in guidelines
            ),
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
            raw = result.get("score")
            valid = (
                isinstance(raw, int)
                and not isinstance(raw, bool)
                and 0 <= raw <= item.max_score
            )
            score = int(raw) if valid else 0
            reason = failure_reason or str(result.get("reason", ""))
            if not failure_reason and not valid:
                reason = f"模型返回非法分数 {raw!r}，保守记 0 分"
            evidence = str(result.get("evidence", "")).strip()
            verdicts.append(
                JudgeVerdict(
                    name=f"guideline.{item.id}",
                    passed=score == item.max_score,
                    score=float(score),
                    max_score=float(item.max_score),
                    reason=reason,
                    evidence=[evidence] if evidence else [],
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
