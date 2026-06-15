"""LLMBackend 单测（change 2026-06-02-share-llm-judge-backend）。

覆盖：
  - provider 分支：openai / azure 客户端类型；azure 缺 base_url/api_version 报错；未知 provider
  - api_key 缺失告警
  - chat_json：RateLimitError 指数退避（patch asyncio.sleep）后成功；超过上限抛出
  - chat_json 返回 json.loads(text) 原始 dict
"""

from __future__ import annotations

import asyncio

import httpx
import pytest
from openai import AsyncAzureOpenAI, AsyncOpenAI, RateLimitError

from medeval import retry as retry_mod
from medeval.judges.llm_backend import LLMBackend


def _rate_limit_error() -> RateLimitError:
    req = httpx.Request("POST", "http://test/chat")
    resp = httpx.Response(429, request=req)
    return RateLimitError("rate limited", response=resp, body=None)


class _Msg:
    def __init__(self, content: str):
        self.content = content


class _Choice:
    def __init__(self, content: str):
        self.message = _Msg(content)


class _Resp:
    def __init__(self, content: str):
        self.choices = [_Choice(content)]


class _FakeCompletions:
    """记录调用次数；前 ``fail_times`` 次抛 RateLimitError，之后返回 ``content``。"""

    def __init__(self, content: str, fail_times: int = 0):
        self.content = content
        self.fail_times = fail_times
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise _rate_limit_error()
        return _Resp(self.content)


class _FakeChat:
    def __init__(self, completions):
        self.completions = completions


class _FakeClient:
    def __init__(self, content: str, fail_times: int = 0):
        self.chat = _FakeChat(_FakeCompletions(content, fail_times))


def test_openai_provider_builds_async_openai():
    backend = LLMBackend(provider="openai", api_key="k")
    assert isinstance(backend._client, AsyncOpenAI)


def test_azure_provider_builds_async_azure_openai():
    backend = LLMBackend(
        provider="azure",
        api_key="k",
        base_url="https://gw.example/openai",
        api_version="2024-02-01",
    )
    assert isinstance(backend._client, AsyncAzureOpenAI)


def test_azure_requires_base_url_and_api_version():
    with pytest.raises(RuntimeError):
        LLMBackend(provider="azure", api_key="k", api_version="2024-02-01")
    with pytest.raises(RuntimeError):
        LLMBackend(provider="azure", api_key="k", base_url="https://gw.example")


def test_unknown_provider_raises():
    with pytest.raises(NotImplementedError):
        LLMBackend(provider="anthropic", api_key="k")


def test_missing_api_key_warns(caplog):
    import logging

    with caplog.at_level(logging.WARNING):
        LLMBackend(provider="openai", api_key="", api_key_env="MEDEVAL_NO_SUCH_KEY")
    assert any("api_key 未设置" in r.message for r in caplog.records)


def test_chat_json_parses_dict():
    backend = LLMBackend(provider="openai", api_key="k")
    backend._client = _FakeClient('{"a": 1, "b": [2, 3]}')
    out = asyncio.run(backend.chat_json("m", "prompt", 0.0))
    assert out == {"a": 1, "b": [2, 3]}


def test_chat_json_retries_then_succeeds(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(s):
        sleeps.append(s)

    monkeypatch.setattr(retry_mod.asyncio, "sleep", fake_sleep)
    backend = LLMBackend(provider="openai", api_key="k")
    backend._client = _FakeClient('{"ok": true}', fail_times=2)
    out = asyncio.run(backend.chat_json("m", "p", 0.0))
    assert out == {"ok": True}
    assert backend._client.chat.completions.calls == 3  # 2 fail + 1 success
    assert len(sleeps) == 2  # 退避了两次


def test_chat_json_raises_after_max_retries(monkeypatch):
    async def fake_sleep(s):
        return None

    monkeypatch.setattr(retry_mod.asyncio, "sleep", fake_sleep)
    backend = LLMBackend(provider="openai", api_key="k")
    backend._client = _FakeClient("{}", fail_times=99)
    with pytest.raises(RateLimitError):
        asyncio.run(backend.chat_json("m", "p", 0.0, max_retries=2))
    assert backend._client.chat.completions.calls == 3  # 初始 + 2 retries
