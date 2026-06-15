"""OpenAI 兼容接口 Adapter —— 适用于 OpenAI / Azure / 火山方舟（豆包）/ DeepSeek 等。

只走标准 `/v1/chat/completions`（messages 数组、stateless 多轮），评测最稳。
依赖 `openai>=1.30`。
"""

from __future__ import annotations

import logging
import os
from typing import Any

from .base import BaseAdapter, ChatRequest, ChatResponse
from .registry import register_adapter

log = logging.getLogger(__name__)


@register_adapter("openai_compat", "openai", "doubao", "ark", config_key="openai_compat")
class OpenAICompatAdapter(BaseAdapter):
    name = "openai_compat"

    def __init__(
        self,
        base_url: str = "",
        model: str = "gpt-4o-mini",
        api_key_env: str = "OPENAI_API_KEY",
        api_key: str = "",
        temperature: float = 0.0,
        max_tokens: int = 1024,
        system_prompt: str = "",
        extra_body: dict[str, Any] | None = None,
        timeout_s: float = 60.0,
    ):
        try:
            from openai import AsyncOpenAI  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "openai package not installed. Run: pip install openai"
            ) from e

        key = api_key or os.environ.get(api_key_env, "")
        if not key:
            raise RuntimeError(
                f"OpenAI-compat adapter requires API key. "
                f"Set env var {api_key_env} or pass api_key in config."
            )

        kwargs: dict[str, Any] = {"api_key": key, "timeout": timeout_s}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = AsyncOpenAI(**kwargs)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.system_prompt = system_prompt
        self.extra_body = extra_body or {}

    async def chat(self, req: ChatRequest) -> ChatResponse:
        messages = list(req.messages)
        if self.system_prompt and not any(m["role"] == "system" for m in messages):
            messages = [{"role": "system", "content": self.system_prompt}, *messages]

        try:
            kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            }
            if self.extra_body:
                kwargs["extra_body"] = self.extra_body

            resp = await self._client.chat.completions.create(**kwargs)
            reply = ""
            if resp.choices:
                reply = resp.choices[0].message.content or ""
            return ChatResponse(
                reply=reply,
                raw={
                    "id": getattr(resp, "id", ""),
                    "model": getattr(resp, "model", ""),
                    "finish_reason": resp.choices[0].finish_reason if resp.choices else "",
                    "usage": resp.usage.model_dump() if getattr(resp, "usage", None) else {},
                },
            )
        except Exception as e:
            log.warning("openai_compat chat failed: %s", e)
            return ChatResponse(reply="", error=f"openai_compat error: {e}")

    async def close(self) -> None:
        try:
            await self._client.close()
        except Exception:
            pass
