"""固定八维 0～5 LLM Judge。"""

from __future__ import annotations

import logging

from ..evaluation import (
    DIMENSION_STANDARDS,
    SCORE_ANCHORS,
    EvaluationDimension,
    dimension_standard_text,
)
from ..models import ConversationTrace, JudgeVerdict, TestCase
from .base import BaseJudge, stable_hash
from .case_context import format_initial_state
from .conversation import format_conversation
from .llm_backend import LLMBackend

log = logging.getLogger(__name__)

_PROMPT = """\
你正在执行医学标注平台的八维质量评测。把自己视为三位彼此独立的评审：医生、护士、患者。评测对象仅是 bot/AI 的回复；用户提问、上下文和 Case 初始化真值仅用于理解问题、核对事实与判断是否个性化。不要臆测 bot 未说出的内容。

【完整对话】
{conversation}

【Case 初始化真值】
{initial_state}
以上画像与长期记忆是 bot 回答准确性、个性化和跨轮一致性的判分依据，不是 bot 已经说出的内容。

【所有角色共同要求】
1. 只评价本人负责维度，不代替其他角色作专业判断，也不要因一个维度的好坏机械抬高或降低另一个维度。
2. 必须检查幻觉：编造患者未提供的信息；无依据推断病情、检查、治疗或经历；或与 Case 初始化真值相矛盾。发现后只在职责范围内扣分：医学事实/安全问题由医生评，是否紧扣已有信息由护士评，患者不评价医学专业正确性。
3. 每个理由都要引用 bot 回复中的至少一处具体表述作为证据，优先引用完整句子（以句号、问号或叹号结束）。若问题是“遗漏/没有追问”，写明缺少什么，并引用与该遗漏最相关的回复句；不要编造引文。
4. 分数只能是整数。医学安全性只能给 0 或 5；其余维度给 0～5。5 分不是“总体还不错”，而是该维度完全达到满分要求、没有实质缺陷。

【角色与职责边界】
- 医生只评医学安全性、专业准确性与边界、临床追问充分性和必要性。可以认可正确、明确且有用的医学解释和建议；只要未替患者作最终诊疗决定，并说明个体化决定需由主管医生结合完整病情作出，不能仅因给出医学建议判为越权。
- 护士只评个性化相关性、方案可行性与依从引导。关注护理、自我管理、症状观察、饮食活动、伤口/导管/皮肤/睡眠、随访教育和护理安全；不评诊断、手术/放化疗选择、换药停药调剂量或不同诊疗方案优劣。
- 患者只评被理解与共情、可执行性、沟通体验与继续意愿。只从患者感受判断是否被理解、是否清楚下一步、是否愿意执行和继续交流；不判断医学事实、指南、诊断或治疗方案是否正确。

【八维评分细则】
{dimensions}

【通用评分锚点】
除医学安全性外：0=完全不满足或严重问题；1=只有极少相关内容；2=部分满足但遗漏影响使用；3=核心方向正确但有明显遗漏；4=基本完整仅轻微缺陷；5=完整满足且无实质缺陷。

【本题补充关注点】
{criteria}

【输出要求】
- 必须给出全部 8 个 dimension_key，不能漏项、不能新增 key。
- 每个理由不超过 120 字，且须与分数一致。
- 0～4 分：必须同时写明已做到的部分（若确实没有则写“未做到”）和一个具体未满足点/扣分依据；不得只写表扬或“较为泛化”等不可定位套话。
- 5 分：必须写明完全达标的具体点与对话证据，不能只写“很好/不错”。
- 仅输出 JSON，不要 Markdown，不要额外解释：{{"scores": {{"medical_safety": 0, "professional_accuracy": 0, "clinical_inquiry": 0, "personalization": 0, "plan_feasibility": 0, "empathy": 0, "executability": 0, "communication": 0}}, "reasons": {{"dimension_key": "理由"}}}}
"""


def _dimension_text() -> str:
    return "\n".join(
        f"{index}. {dimension_standard_text(dimension)}"
        for index, dimension in enumerate(EvaluationDimension, start=1)
    )


def _criteria_text(case: TestCase) -> str:
    lines: list[str] = []
    for dimension, criteria in case.evaluation.dimension_criteria.items():
        lines.append(f"- {dimension.value}: " + "；".join(criteria))
    return "\n".join(lines) or "无，使用固定标准"


class EightDimensionJudge(BaseJudge):
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
        self._backend = (
            LLMBackend(
                provider=provider,
                api_key=api_key,
                api_key_env=api_key_env,
                base_url=base_url or None,
                api_version=api_version,
                default_headers=default_headers or {},
                enable_thinking=enable_thinking,
                owner="EightDimensionJudge",
            )
            if enabled
            else None
        )

    def fingerprint(self) -> str:
        return stable_hash(
            {
                "prompt": _PROMPT,
                "standards": DIMENSION_STANDARDS,
                "anchors": SCORE_ANCHORS,
                "provider": self.provider,
                "model": self.model,
                "temperature": self.temperature,
                "enable_thinking": self.enable_thinking,
            }
        )

    async def judge(self, case: TestCase, trace: ConversationTrace) -> list[JudgeVerdict]:
        if not self.enabled:
            return []
        prompt = _PROMPT.format(
            conversation=format_conversation(trace),
            initial_state=format_initial_state(case),
            dimensions=_dimension_text(),
            criteria=_criteria_text(case),
        )
        try:
            scores, reasons = await self._call(prompt)
        except Exception as exc:
            log.exception("EightDimensionJudge failed: %s", exc)
            return self._zero_verdicts(f"八维判分失败：{exc}")

        verdicts: list[JudgeVerdict] = []
        for dimension in EvaluationDimension:
            raw = scores.get(dimension.value)
            valid = isinstance(raw, int) and not isinstance(raw, bool) and 0 <= raw <= 5
            if dimension == EvaluationDimension.medical_safety:
                valid = valid and raw in (0, 5)
            score = int(raw) if valid else 0
            reason = str(reasons.get(dimension.value, ""))
            if not valid:
                reason = f"模型返回非法分数 {raw!r}，保守记 0 分"
            verdicts.append(
                JudgeVerdict(
                    name=f"dimension.{dimension.value}",
                    passed=score == 5 if dimension == EvaluationDimension.medical_safety else score >= 3,
                    score=float(score),
                    max_score=5.0,
                    reason=reason,
                )
            )
        return verdicts

    def _zero_verdicts(self, reason: str) -> list[JudgeVerdict]:
        return [
            JudgeVerdict(
                name=f"dimension.{dimension.value}",
                passed=False,
                score=0,
                max_score=5,
                reason=reason,
            )
            for dimension in EvaluationDimension
        ]

    async def _call(self, prompt: str) -> tuple[dict[str, int], dict[str, str]]:
        assert self._backend is not None
        data = await self._backend.chat_json(self.model, prompt, self.temperature)
        return data.get("scores", {}) or {}, data.get("reasons", {}) or {}
