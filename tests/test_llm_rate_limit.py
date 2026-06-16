"""LLM 判官全局限流与 QPM 退避。"""

from __future__ import annotations

import asyncio

import httpx
import pytest
from openai import RateLimitError

from medeval import retry as retry_mod
from medeval.judges.llm_backend import (
    LLMBackend,
    configure_llm_rate_limit,
    reset_llm_rate_limit,
)


def _rate_limit_error(message: str = "rate limited") -> RateLimitError:
    req = httpx.Request("POST", "http://test/chat")
    resp = httpx.Response(429, request=req)
    return RateLimitError(message, response=resp, body=None)


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
    def __init__(self, content: str, fail_times: int = 0, message: str = "rate limited"):
        self.content = content
        self.fail_times = fail_times
        self.message = message
        self.calls = 0
        self._lock = asyncio.Lock()

    async def create(self, **kwargs):
        async with self._lock:
            self.calls += 1
            if self.calls <= self.fail_times:
                raise _rate_limit_error(self.message)
        return _Resp(self.content)


class _FakeChat:
    def __init__(self, completions):
        self.completions = completions


class _FakeClient:
    def __init__(self, content: str, fail_times: int = 0, message: str = "rate limited"):
        self.chat = _FakeChat(_FakeCompletions(content, fail_times, message))


@pytest.fixture(autouse=True)
def _reset_gate():
    reset_llm_rate_limit()
    yield
    reset_llm_rate_limit()


def test_qpm_error_waits_at_least_60s(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(s):
        sleeps.append(s)

    monkeypatch.setattr(retry_mod.asyncio, "sleep", fake_sleep)
    backend = LLMBackend(provider="openai", api_key="k")
    backend._client = _FakeClient('{"ok": true}', fail_times=1, message="qpm limit")
    out = asyncio.run(backend.chat_json("m", "p", 0.0, max_retries=2))
    assert out == {"ok": True}
    assert any(s >= 60.0 for s in sleeps)


def test_global_gate_serializes_concurrent_calls():
    configure_llm_rate_limit(1, min_interval_s=0.0)
    backend = LLMBackend(provider="openai", api_key="k")
    comp = _FakeCompletions('{"ok": true}', fail_times=0)
    backend._client = type("C", (), {"chat": _FakeChat(comp)})()

    async def run_two():
        await asyncio.gather(
            backend.chat_json("m", "a", 0.0),
            backend.chat_json("m", "b", 0.0),
        )

    asyncio.run(run_two())
    assert comp.calls == 2
