"""通用 HTTP Adapter —— 把你自己的 chatbot HTTP 接口接进来。

设计：
  * body_template 是一段 JSON 字符串模板，支持两个占位符：
      {{messages}}    —— OpenAI 风格 messages 数组（list[dict]）
      {{session_id}}  —— 会话 ID
  * response_path 用点路径从响应里提取 assistant reply，例如 "data.reply"
  * headers 支持 ${ENV_VAR} 形式的环境变量插值

如果你的接口结构更复杂，建议直接在 adapter/ 下新增一个自定义 adapter。
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

from .base import BaseAdapter, ChatRequest, ChatResponse
from .registry import register_adapter


_ENV_PATTERN = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


def _interpolate_env(value: str) -> str:
    def _sub(m):
        return os.environ.get(m.group(1), m.group(0))

    return _ENV_PATTERN.sub(_sub, value)


def _get_by_path(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


@register_adapter("http", config_key="http")
class HttpAdapter(BaseAdapter):
    name = "http"

    def __init__(
        self,
        base_url: str,
        endpoint: str = "/chat",
        method: str = "POST",
        headers: dict[str, str] | None = None,
        body_template: str = '{"messages": {{messages}}, "session_id": "{{session_id}}"}',
        response_path: str = "reply",
        timeout_s: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.endpoint = endpoint
        self.method = method.upper()
        self.headers = {k: _interpolate_env(v) for k, v in (headers or {}).items()}
        self.body_template = body_template
        self.response_path = response_path
        self._client = httpx.AsyncClient(timeout=timeout_s)

    async def chat(self, req: ChatRequest) -> ChatResponse:
        body_str = self.body_template.replace(
            "{{messages}}", json.dumps(req.messages, ensure_ascii=False)
        ).replace("{{session_id}}", req.session_id)
        try:
            body = json.loads(body_str)
        except json.JSONDecodeError as e:
            return ChatResponse(reply="", error=f"body_template invalid JSON: {e}")

        try:
            resp = await self._client.request(
                self.method,
                self.base_url + self.endpoint,
                headers=self.headers,
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()
            reply = _get_by_path(data, self.response_path) or ""
            return ChatResponse(reply=str(reply), raw=data)
        except Exception as e:
            return ChatResponse(reply="", error=f"http error: {e}")

    async def close(self) -> None:
        await self._client.aclose()
