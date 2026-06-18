"""LLMBackend —— 所有走 LLM 的判官共用的 client 构建 + 限速退避调用层。

参见 OpenSpec change ``2026-06-02-share-llm-judge-backend``。

LLMJudge / ScoringPointJudge / SemanticRuleAdjudicator 原先各自复制了一套
``_build_client``（openai/azure 双分支）与 ``_call``（``RateLimitError`` 指数退避）。
这里把这层正交的 IO 关注点收敛到一个可注入的后端：判官只保留各自的 prompt 组装
与返回 JSON 的结构解析。

约束：
  * 该后端的调用配置（api_key / base_url / api_version / default_headers）**不进入**
    任何判官的 ``fingerprint()`` —— 切镜像 / 切网关不应被误判为判分逻辑变化。
  * ``chat_json`` 返回 ``json.loads(text)`` 原始 dict，由各判官自行解析。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from ..retry import backoff_delay, retry_async

log = logging.getLogger(__name__)

# 火山方舟 / AIDP 等对单 endpoint 有 QPM 限速；OpenAI SDK 内置重试间隔过短。
# 默认最多 6 次额外重试；QPM 命中时单次退避至少 60s。
_DEFAULT_MAX_RETRIES = 6
_QPM_MIN_BACKOFF_S = 60.0

_gate: asyncio.Semaphore | None = None
_min_interval_s: float = 0.0
_interval_lock: asyncio.Lock | None = None
_last_call_at: float = 0.0


def configure_llm_rate_limit(max_concurrent: int, min_interval_s: float = 0.0) -> None:
    """评测 judge 阶段启动前调用：全局限流 llm / scoring_point / semantic 的 chat_json。"""
    global _gate, _min_interval_s, _interval_lock, _last_call_at
    max_concurrent = max(1, int(max_concurrent))
    _gate = asyncio.Semaphore(max_concurrent)
    _min_interval_s = max(0.0, float(min_interval_s))
    _interval_lock = asyncio.Lock()
    _last_call_at = 0.0


def reset_llm_rate_limit() -> None:
    """测试辅助：清除全局限流状态。"""
    global _gate, _min_interval_s, _interval_lock, _last_call_at
    _gate = None
    _min_interval_s = 0.0
    _interval_lock = None
    _last_call_at = 0.0


async def _acquire_llm_slot() -> None:
    global _last_call_at
    if _gate is None:
        return
    await _gate.acquire()
    if _min_interval_s <= 0 or _interval_lock is None:
        return
    async with _interval_lock:
        wait = _min_interval_s - (time.monotonic() - _last_call_at)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_call_at = time.monotonic()


def _release_llm_slot() -> None:
    if _gate is not None:
        _gate.release()


def _is_rate_limit_error(exc: BaseException) -> bool:
    from openai import RateLimitError  # type: ignore

    if isinstance(exc, RateLimitError):
        return True
    msg = str(exc).lower()
    return "429" in msg or "rate limit" in msg or "qpm" in msg


def _delay_for_rate_limit(attempt: int, exc: BaseException) -> float | None:
    if not _is_rate_limit_error(exc):
        return None
    base_delay = backoff_delay(
        attempt, base=5.0, factor=2.0, max_delay=40.0, jitter=2.0
    )
    if "qpm" in str(exc).lower():
        return max(base_delay, _QPM_MIN_BACKOFF_S)
    return base_delay


class LLMBackend:
    """统一的 LLM client 构建 + 限速退避调用。

    ``owner`` 仅用于日志可读性（区分是哪个判官触发的告警/退避），不影响行为、不进指纹。
    """

    def __init__(
        self,
        provider: str = "openai",
        api_key: str = "",
        api_key_env: str = "OPENAI_API_KEY",
        base_url: str | None = None,
        api_version: str = "",
        default_headers: dict[str, str] | None = None,
        owner: str = "LLM",
    ):
        self.provider = provider
        self.api_key = api_key
        self.api_key_env = api_key_env
        self.base_url = base_url or None
        self.api_version = api_version
        self.default_headers = default_headers or {}
        self.owner = owner
        self._client = self._build_client()

    def _build_client(self):
        import os

        api_key = self.api_key or os.environ.get(self.api_key_env, "")
        if not api_key:
            log.warning(
                "%s enabled 但 api_key 未设置（config.api_key 和环境变量 %s 都为空）",
                self.owner,
                self.api_key_env,
            )

        if self.provider == "azure":
            # 字节 AIDP / Azure OpenAI / 任何走 Azure 协议的网关
            try:
                from openai import AsyncAzureOpenAI  # type: ignore
            except ImportError as e:
                raise RuntimeError(
                    "openai package not installed. Run: pip install openai"
                ) from e
            if not self.base_url:
                raise RuntimeError(
                    "provider=azure 时必须配置 base_url（即 azure_endpoint）"
                )
            if not self.api_version:
                raise RuntimeError(
                    "provider=azure 时必须配置 api_version（如 '2024-02-01'）"
                )
            kwargs: dict[str, Any] = {
                "api_key": api_key or "dummy",
                "api_version": self.api_version,
                "azure_endpoint": self.base_url,
            }
            if self.default_headers:
                kwargs["default_headers"] = self.default_headers
            return AsyncAzureOpenAI(**kwargs)

        if self.provider == "openai":
            try:
                from openai import AsyncOpenAI  # type: ignore
            except ImportError as e:
                raise RuntimeError(
                    "openai package not installed. Run: pip install openai"
                ) from e
            kwargs = {"api_key": api_key or "dummy"}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            if self.default_headers:
                kwargs["default_headers"] = self.default_headers
            return AsyncOpenAI(**kwargs)

        raise NotImplementedError(
            f"{self.owner} provider '{self.provider}' not implemented. "
            f"支持的值：openai, azure。"
        )

    async def chat_json(
        self,
        model: str,
        prompt: str,
        temperature: float = 0.0,
        max_retries: int = _DEFAULT_MAX_RETRIES,
    ) -> dict[str, Any]:
        """单条 user prompt → 严格 JSON 响应，带限速指数退避。返回 ``json.loads(text)``。

        退避数学复用 ``medeval.retry``（单一真值源）：``min(40, 5*2^attempt + U(0,2))``；
        QPM 限频时单次退避至少 60s。调用前受 ``configure_llm_rate_limit`` 全局限流。
        """
        from openai import RateLimitError  # type: ignore  # noqa: F401 — retryable 类型

        async def _create():
            return await self._client.chat.completions.create(  # type: ignore[union-attr]
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                response_format={"type": "json_object"},
            )

        def _on_retry(attempt: int, exc: BaseException, wait: float) -> None:
            log.warning(
                "%s 触发限速 (尝试 %d/%d)，等待 %.1fs 重试%s",
                self.owner,
                attempt + 1,
                max_retries + 1,
                wait,
                " [QPM]" if "qpm" in str(exc).lower() else "",
            )

        await _acquire_llm_slot()
        try:
            resp = await retry_async(
                _create,
                max_retries=max_retries,
                retryable=_is_rate_limit_error,
                base=5.0,
                factor=2.0,
                max_delay=40.0,
                jitter=2.0,
                on_retry=_on_retry,
                delay_for=_delay_for_rate_limit,
            )
        finally:
            _release_llm_slot()
        text = resp.choices[0].message.content or "{}"
        return json.loads(text)


def backend_from_llm_cfg(cfg, *, owner: str = "LLM") -> LLMBackend:
    """从 LLMJudgeCfg（或同形对象）构造 LLMBackend。"""
    return LLMBackend(
        provider=cfg.provider,
        api_key=cfg.api_key,
        api_key_env=cfg.api_key_env,
        base_url=cfg.base_url or None,
        api_version=cfg.api_version,
        default_headers=cfg.default_headers,
        owner=owner,
    )
