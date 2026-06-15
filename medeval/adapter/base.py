"""Adapter 抽象基类。

医疗 chatbot 评测对接口的要求：
  * 支持多轮对话（必须能传完整 history）
  * 支持 session_id（同一通对话所有 turn 应保持上下文）
  * 必须能拿到结构化 raw_response（便于排查 hallucination、检索失败等）

实现一个新 adapter：
  1. 继承 BaseAdapter
  2. 实现 async def chat(req: ChatRequest) -> ChatResponse
  3. 在 adapter/__init__.py 的 build_adapter() 注册类型名
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChatRequest:
    messages: list[dict[str, str]]    # OpenAI 风格 [{role, content}]
    session_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatResponse:
    reply: str
    raw: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class BaseAdapter(ABC):
    """Adapter 必须是异步的，便于 Runner 做高并发。"""

    name: str = "base"

    @abstractmethod
    async def chat(self, req: ChatRequest) -> ChatResponse:  # pragma: no cover
        ...

    async def close(self) -> None:
        """资源释放钩子，子类可重写。"""
        return None
