"""ScoringPointJudge —— HealthBench 式专家得分点逐点打分。

设计：
  * 仅对声明了 ``case.scoring_points`` 的用例生效；空则直接返回 []、零 API 调用。
  * 用 LLM grader 对每个得分点逐条判 met/未met，输出严格 JSON。
  * 支持负分：正分=应满足；负分=出现即惩罚（命中即扣分）。
  * 产出软分（不阻塞 gate_passed），并派生指南匹配率（仅度量、不否决）。
  * 作为 LLM 判官，在 N-runs 下只对代表性 trace 调用一次（由 CLI 调度）。

参见 OpenSpec change add-scoring-point-judge。
"""

from __future__ import annotations

import logging

from ..models import ConversationTrace, JudgeVerdict, ScoringPoint, TestCase
from .base import BaseJudge, stable_hash
from .llm import _format_conversation
from .llm_backend import LLMBackend

log = logging.getLogger(__name__)


_PROMPT_TEMPLATE = """\
你是一名严格的医疗 chatbot 评测员。下面给出一段完整对话，以及一组由临床专家预先编写的"得分点"。请仅依据 bot 的回复（[turn N · bot] 标注的轮次）逐条判断每个得分点是否"命中（met）"。

【完整对话历史（按时间顺序）】
{conversation}

【待判定的得分点（按编号）】
{points_text}

【判定说明】
- met=true 表示 bot 回复确实满足/出现了该得分点描述的内容；met=false 表示未满足/未出现。
- 只看 bot 实际说出的内容，不要替 bot 脑补；用户说的内容不算 bot 的功劳或失误。
- 对"出现即惩罚"类得分点（描述某种不应出现的内容），只要 bot 回复确实出现了该内容即 met=true。

【输出要求】
仅输出 JSON，不要 markdown 包裹。按编号顺序给出每个得分点的判定：
{{
  "results": [ {{ "index": <int>, "met": <bool>, "reason": "<≤40字理由>" }}, ... ]
}}
"""


def _format_points(points: list[ScoringPoint]) -> str:
    lines = []
    for i, sp in enumerate(points, start=1):
        sign = "应满足" if sp.points > 0 else "出现即惩罚"
        lines.append(f"{i}. [{sign}/{sp.points:+d}] {sp.criterion}")
    return "\n".join(lines)


def _normalize_score(achieved: int, max_positive: int, any_negative_hit: bool) -> float:
    """归一化得分（含负分语义与 max_positive==0 边界）。

    * max_positive > 0 → clip(achieved / max_positive, 0, 1)
    * max_positive == 0（只含负分点）→ 无负分命中记 1.0，有负分命中记 0.0
    """
    if max_positive > 0:
        return max(0.0, min(achieved / max_positive, 1.0))
    return 0.0 if any_negative_hit else 1.0


def compute_guideline_match_rate(
    case: TestCase, verdicts: list[JudgeVerdict]
) -> float | None:
    """从带 guideline 锚点的得分点派生指南匹配率（按点计数）。

    命中 = 该点达到"期望状态"（正分点被满足 / 负分点未出现），即 per-point
    verdict 的 ``passed``。无带锚点的得分点时返回 None（不计入聚合分母）。
    """
    passed_by_idx: dict[int, bool] = {}
    prefix = "scoring_point.point"
    for v in verdicts:
        if v.name.startswith(prefix):
            try:
                idx = int(v.name[len(prefix):])
            except ValueError:
                continue
            passed_by_idx[idx] = v.passed

    guideline_idxs = [i for i, sp in enumerate(case.scoring_points) if sp.guideline]
    if not guideline_idxs:
        return None
    matched = sum(1 for i in guideline_idxs if passed_by_idx.get(i, False))
    return matched / len(guideline_idxs)


class ScoringPointJudge(BaseJudge):
    name = "scoring_point"

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
        # self-consistency 多采样（参见 change decouple-scoring-axes）。
        self_consistency: int = 1,
    ):
        self.enabled = enabled
        self.provider = provider
        self.model = model
        self.api_key_env = api_key_env
        self.api_key = api_key
        self.base_url = base_url or None
        self.temperature = temperature
        self.api_version = api_version
        self.default_headers = default_headers or {}
        # K=1 → 与未引入本能力前完全一致；K>1 → 对同一 trace 调 K 次，逐点 majority vote。
        self.self_consistency = max(1, int(self_consistency or 1))
        self._backend: LLMBackend | None = None
        if enabled:
            self._backend = LLMBackend(
                provider=self.provider,
                api_key=self.api_key,
                api_key_env=self.api_key_env,
                base_url=self.base_url,
                api_version=self.api_version,
                default_headers=self.default_headers,
                owner="ScoringPointJudge",
            )

    def fingerprint(self) -> str:
        """覆盖 prompt 模板 + provider + model + temperature + enabled + self-consistency。

        不覆盖 case 的得分点内容（属用例数据，不纳入 fingerprint）；
        排除 api_key / base_url / api_version 等调用配置。
        """
        return stable_hash(
            {
                "prompt_template": _PROMPT_TEMPLATE,
                "provider": self.provider,
                "model": self.model,
                "temperature": self.temperature,
                "enabled": self.enabled,
                "self_consistency": self.self_consistency,
            }
        )

    async def judge(
        self, case: TestCase, trace: ConversationTrace
    ) -> list[JudgeVerdict]:
        points = case.scoring_points
        if not points:
            return []  # 无得分点：零 API 调用
        if not self.enabled:
            return []

        prompt = _PROMPT_TEMPLATE.format(
            conversation=_format_conversation(trace),
            points_text=_format_points(points),
        )

        try:
            if self.self_consistency <= 1:
                met_by_index, reason_by_index = await self._call(prompt)
                met = [bool(met_by_index.get(i + 1, False)) for i in range(len(points))]
                reasons = [str(reason_by_index.get(i + 1, "")) for i in range(len(points))]
                dispersion = [0.0] * len(points)
            else:
                samples_met: list[dict[int, bool]] = []
                samples_reason: list[dict[int, str]] = []
                for _ in range(self.self_consistency):
                    m, r = await self._call(prompt)
                    samples_met.append(m)
                    samples_reason.append(r)
                met, reasons, dispersion = self._aggregate_samples(
                    len(points), samples_met, samples_reason
                )
        except Exception as e:
            log.exception("ScoringPointJudge failed: %s", e)
            return self._build_verdicts(
                points,
                met=[False] * len(points),
                reasons=[f"得分点判定失败：{e}"] * len(points),
                failed=True,
            )

        return self._build_verdicts(
            points, met=met, reasons=reasons, failed=False, dispersion=dispersion
        )

    def _aggregate_samples(
        self,
        n_points: int,
        samples_met: list[dict[int, bool]],
        samples_reason: list[dict[int, str]],
    ) -> tuple[list[bool], list[str], list[float]]:
        """逐点 majority vote 聚合 K 次采样：met 多数票（平票→未命中），dispersion=分歧占比。"""
        k = len(samples_met)
        met: list[bool] = []
        reasons: list[str] = []
        dispersion: list[float] = []
        for i in range(n_points):
            votes = [bool(samples_met[j].get(i + 1, False)) for j in range(k)]
            true_count = sum(votes)
            is_met = true_count * 2 > k  # 严格多数；平票算未命中
            met.append(is_met)
            dispersion.append(min(true_count, k - true_count) / k if k else 0.0)
            # 取与多数票一致的那次采样的理由。
            reason = ""
            for j in range(k):
                if bool(samples_met[j].get(i + 1, False)) == is_met:
                    reason = str(samples_reason[j].get(i + 1, ""))
                    break
            reasons.append(reason)
        return met, reasons, dispersion

    def _build_verdicts(
        self,
        points: list[ScoringPoint],
        met: list[bool],
        reasons: list[str],
        failed: bool,
        dispersion: list[float] | None = None,
    ) -> list[JudgeVerdict]:
        verdicts: list[JudgeVerdict] = []
        achieved = 0
        max_positive = 0
        any_negative_hit = False
        hit_count = 0

        for i, sp in enumerate(points):
            is_met = met[i]
            # 期望状态：正分点应被满足；负分点应不出现。
            desired = is_met if sp.points > 0 else (not is_met)
            point_score = sp.points if is_met else 0
            achieved += point_score
            if sp.points > 0:
                max_positive += sp.points
            if is_met:
                hit_count += 1
                if sp.points < 0:
                    any_negative_hit = True
            mark = "✓" if desired else "✗"
            verdicts.append(
                JudgeVerdict(
                    name=f"scoring_point.point{i}",
                    passed=desired,
                    score=float(point_score),
                    max_score=float(sp.points if sp.points > 0 else 0),
                    reason=reasons[i],
                    evidence=[f"[{mark} {sp.points:+d}] {sp.criterion}"],
                    score_dispersion=(
                        float(dispersion[i]) if dispersion is not None else 0.0
                    ),
                )
            )

        normalized = _normalize_score(achieved, max_positive, any_negative_hit)
        summary_reason = (
            f"得分点判定失败（降级为全部未命中）"
            if failed
            else f"命中 {hit_count}/{len(points)} 个得分点，净得分 {achieved}/{max_positive}，归一化 {normalized:.2f}"
        )
        verdicts.append(
            JudgeVerdict(
                name="scoring_point.summary",
                passed=(not failed) and normalized >= 0.5,
                score=float(achieved),
                max_score=float(max_positive),
                reason=summary_reason,
                evidence=[v.evidence[0] for v in verdicts],
            )
        )
        return verdicts

    async def _call(self, prompt: str) -> tuple[dict[int, bool], dict[int, str]]:
        """单次逐点判定；client 构建与限速退避由共享 ``LLMBackend`` 负责。"""
        assert self._backend is not None  # enabled 时已构造
        data = await self._backend.chat_json(self.model, prompt, self.temperature)
        results = data.get("results", []) or []
        met: dict[int, bool] = {}
        reasons: dict[int, str] = {}
        for item in results:
            try:
                idx = int(item["index"])
            except (KeyError, TypeError, ValueError):
                continue
            met[idx] = bool(item.get("met", False))
            reasons[idx] = str(item.get("reason", ""))
        return met, reasons
