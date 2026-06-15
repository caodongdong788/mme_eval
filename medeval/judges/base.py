"""Judge 抽象基类。"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from typing import Any

from ..models import ConversationTrace, JudgeVerdict, TestCase


def stable_hash(payload: Any) -> str:
    """对任意 JSON 可序列化对象计算稳定哈希 (sha1 前 12 位).

    跨平台 / 跨 Python 版本稳定：
      * sort_keys=True 保证 dict 的键序无关
      * ensure_ascii=False 避免中文转义不一致
      * 输出固定 12 位 hex (48 bit, 碰撞概率 ~4e-12 在 50 版本下)

    在 ``BaseJudge.fingerprint`` 中使用，该哈希被写进
    ``JudgeVerdict.judge_fingerprint`` 与 ``RunReport.judge_fingerprints``，
    用于在 ``diff_runs`` 中识别"判分逻辑变化导致的伪差异"。
    """

    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:12]


class BaseJudge(ABC):
    name: str = "base"

    @abstractmethod
    async def judge(
        self, case: TestCase, trace: ConversationTrace
    ) -> list[JudgeVerdict]:
        """一个 judge 可以返回多个 verdict（例如硬门槛分别返回三个）。"""

    @abstractmethod
    def fingerprint(self) -> str:
        """返回该 Judge 实例的稳定 12 位哈希。

        必须覆盖所有"会影响判分输出"的静态属性（patterns / prompt /
        normalization / 实例配置）。注释改动不应改变 fingerprint。

        实现细节参见各子类；漂移保护单测在
        ``tests/test_judge_fingerprint.py::test_known_fingerprints``。
        """

    @staticmethod
    def _assistant_replies(trace: ConversationTrace) -> list[str]:
        return [m.content for m in trace.messages if m.role == "assistant"]

    @staticmethod
    def _last_reply(trace: ConversationTrace) -> str:
        replies = [m.content for m in trace.messages if m.role == "assistant"]
        return replies[-1] if replies else ""

    @staticmethod
    def _full_reply(trace: ConversationTrace) -> str:
        """所有 assistant 回复拼起来，便于跨轮匹配。"""
        return "\n".join(m.content for m in trace.messages if m.role == "assistant")
