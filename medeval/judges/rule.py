"""Rule Judge —— 用例侧声明的 must_have / must_not_have 校验。

* must_have：默认 OR（任一命中即通过）；若 must_have_all=True 则改为 AND。
* must_not_have：任何一个命中即 fail。

匹配前做归一化：全角->半角、繁简通用化（这里仅做大小写、空白归一）。
医疗术语对大小写不敏感，对全角半角空格不敏感即可。
"""

from __future__ import annotations

import json
import re
import unicodedata

import inspect

from ..models import (
    ConversationTrace,
    FailureTag,
    JudgeVerdict,
    OutputCheck,
    OutputCheckKind,
    Pattern,
    TestCase,
)
from .base import BaseJudge, stable_hash


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _match(pattern: Pattern, text: str) -> tuple[bool, str]:
    if pattern.regex:
        m = re.search(pattern.regex, text)
        if m:
            return True, m.group(0)
        return False, ""
    if pattern.keyword:
        kw = _normalize(pattern.keyword)
        if kw in _normalize(text):
            return True, pattern.keyword
        return False, ""
    return False, ""


def _eval_output_check(check: OutputCheck, reply: str) -> tuple[bool, str]:
    """对单条结构化 Output Check 做确定性判定，返回 (passed, ≤40字 reason)。

    全部零 LLM 调用、纯文本 / 标准库 JSON 解析。未知 kind 视为不通过（防漏判）。
    """
    kind = check.kind
    params = check.params or {}

    if kind == OutputCheckKind.MAX_CHARS:
        limit = int(params.get("max", 0))
        n = len(reply)
        return (n <= limit, f"长度 {n} ≤ {limit}" if n <= limit else f"超长 {n}>{limit}")

    if kind == OutputCheckKind.MIN_CHARS:
        limit = int(params.get("min", 0))
        n = len(reply)
        return (n >= limit, f"长度 {n} ≥ {limit}" if n >= limit else f"过短 {n}<{limit}")

    if kind == OutputCheckKind.MUST_CONTAIN:
        pat = str(params.get("pattern", ""))
        if params.get("regex"):
            hit = bool(re.search(pat, reply))
        else:
            hit = pat in reply
        return (hit, "命中必含" if hit else f"缺必含「{pat}」")

    if kind == OutputCheckKind.FORBID_REGEX:
        pat = str(params.get("pattern", ""))
        hit = bool(re.search(pat, reply))
        return (not hit, "未命中禁含" if not hit else f"命中禁含「{pat}」")

    if kind == OutputCheckKind.JSON_VALID:
        try:
            json.loads(reply)
            return True, "JSON 合法"
        except (ValueError, TypeError):
            return False, "非合法 JSON"

    if kind == OutputCheckKind.REQUIRED_FIELDS:
        fields = [str(f) for f in (params.get("fields") or [])]
        try:
            obj = json.loads(reply)
        except (ValueError, TypeError):
            return False, "非合法 JSON"
        if not isinstance(obj, dict):
            return False, "JSON 非对象"
        missing = [f for f in fields if f not in obj]
        return (not missing, "字段齐全" if not missing else f"缺字段 {missing}")

    return False, f"未知 Output Check 类型：{kind}"


class RuleJudge(BaseJudge):
    name = "rule"

    def __init__(self, normalize: bool = True):
        self.normalize = normalize

    def fingerprint(self) -> str:
        """覆盖归一化函数源码 + Output Check 判定源码 + 实例配置 normalize 开关."""
        return stable_hash(
            {
                "normalize_source": inspect.getsource(_normalize),
                "output_check_source": inspect.getsource(_eval_output_check),
                "normalize_flag": self.normalize,
            }
        )

    async def judge(
        self, case: TestCase, trace: ConversationTrace
    ) -> list[JudgeVerdict]:
        text = self._full_reply(trace)
        if self.normalize:
            text_norm = _normalize(text)
        else:
            text_norm = text

        results: list[JudgeVerdict] = []
        results.append(self._check_must_have(case, text))
        results.append(self._check_must_not_have(case, text))
        results.extend(self._check_output_checks(case, text))
        return results

    def _check_output_checks(
        self, case: TestCase, text: str
    ) -> list[JudgeVerdict]:
        """逐条结构化 Output Check：空声明返回 []（零行为变化）。

        每条产出 ``rule.output_check{i}`` verdict；失败附 CONSTRAINT_VIOLATION。
        """
        checks = case.expected_behavior.output_checks
        verdicts: list[JudgeVerdict] = []
        for i, check in enumerate(checks):
            passed, reason = _eval_output_check(check, text)
            verdicts.append(
                JudgeVerdict(
                    name=f"rule.output_check{i}",
                    passed=passed,
                    score=1.0 if passed else 0.0,
                    max_score=1.0,
                    reason=f"[{check.kind.value}] {reason}",
                    failure_tags=(
                        [] if passed else [FailureTag.CONSTRAINT_VIOLATION]
                    ),
                )
            )
        return verdicts

    # ------------------------------------------------------------------

    def _check_must_have(self, case: TestCase, text: str) -> JudgeVerdict:
        eb = case.expected_behavior
        if not eb.must_have:
            return JudgeVerdict(
                name="rule.must_have",
                passed=True,
                score=1.0,
                max_score=1.0,
                reason="N/A",
            )

        evidence: list[str] = []
        missing_patterns: list[Pattern] = []
        for p in eb.must_have:
            hit, ev = _match(p, text)
            if hit:
                evidence.append(ev)
            else:
                missing_patterns.append(p)

        if eb.must_have_all:
            passed = not missing_patterns
            reason = (
                "全部命中"
                if passed
                else "must_have 部分未命中（要求全部命中）"
            )
            unmet = [] if passed else missing_patterns
        else:
            passed = bool(evidence)
            reason = (
                f"命中：{', '.join(evidence)}"
                if passed
                else "全部 must_have 均未命中（期望任一命中）"
            )
            unmet = [] if passed else list(eb.must_have)

        tags: list[FailureTag] = (
            [FailureTag.INQUIRY_INCOMPLETE] if not passed else []
        )
        return JudgeVerdict(
            name="rule.must_have",
            passed=passed,
            score=1.0 if passed else 0.0,
            max_score=1.0,
            reason=reason,
            evidence=evidence,
            unmet_patterns=unmet,
            failure_tags=tags,
        )

    def _check_must_not_have(self, case: TestCase, text: str) -> JudgeVerdict:
        eb = case.expected_behavior
        if not eb.must_not_have:
            return JudgeVerdict(
                name="rule.must_not_have",
                passed=True,
                score=1.0,
                max_score=1.0,
                reason="N/A",
            )

        hits: list[str] = []
        for p in eb.must_not_have:
            hit, ev = _match(p, text)
            if hit:
                hits.append(ev)

        if hits:
            return JudgeVerdict(
                name="rule.must_not_have",
                passed=False,
                score=0.0,
                max_score=1.0,
                reason=f"命中禁含：{', '.join(hits)}",
                evidence=hits,
                failure_tags=[FailureTag.CONSTRAINT_VIOLATION],
            )
        return JudgeVerdict(
            name="rule.must_not_have",
            passed=True,
            score=1.0,
            max_score=1.0,
            reason="未命中任何禁含项",
        )
