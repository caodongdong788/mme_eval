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
from contextvars import ContextVar
from dataclasses import dataclass
import inspect
import json
import logging
import time
from typing import Any, Awaitable, Callable

from ..retry import backoff_delay, retry_async

log = logging.getLogger(__name__)

# 火山方舟 / AIDP 等对单 endpoint 有 QPM 限速；OpenAI SDK 内置重试间隔过短。
# 默认最多 6 次额外重试；QPM 命中时单次退避至少 60s。
_DEFAULT_MAX_RETRIES = 6
_QPM_MIN_BACKOFF_S = 60.0
# 判分属于后台任务，允许模型完成一次复杂推理；但不能无限等待单个请求。
JUDGE_REQUEST_TIMEOUT_S = 300.0

@dataclass
class _RateLimitState:
    gate: asyncio.Semaphore
    min_interval_s: float
    interval_lock: asyncio.Lock
    last_call_at: float = 0.0


# 每个 Durable Worker 任务拥有自己的稳定限流状态。旧实现会在并行任务启动时
# 替换进程全局 semaphore，导致请求取得旧 semaphore 后却释放新 semaphore，
# 旧队列永久无法唤醒；归因任务也可能继承上一次离线重判遗留的限流器。
_rate_limit_state: ContextVar[_RateLimitState | None] = ContextVar(
    "mme_llm_rate_limit_state", default=None
)


def is_kimi_k3_model(model: str | None) -> bool:
    """Kimi K3 的 DashScope 标准模型名（兼容旧配置别名）。"""
    return str(model or "").strip().lower() in {"kimi-k3", "kimi/kimi-k3"}


def configure_llm_rate_limit(max_concurrent: int, min_interval_s: float = 0.0) -> None:
    """评测 judge 阶段启动前调用：全局限流八维与指南 chat_json。"""
    max_concurrent = max(1, int(max_concurrent))
    _rate_limit_state.set(
        _RateLimitState(
            gate=asyncio.Semaphore(max_concurrent),
            min_interval_s=max(0.0, float(min_interval_s)),
            interval_lock=asyncio.Lock(),
        )
    )


def reset_llm_rate_limit() -> None:
    """测试辅助：清除全局限流状态。"""
    _rate_limit_state.set(None)


async def _acquire_llm_slot() -> _RateLimitState | None:
    state = _rate_limit_state.get()
    if state is None:
        return None
    await state.gate.acquire()
    if state.min_interval_s <= 0:
        return state
    async with state.interval_lock:
        wait = state.min_interval_s - (time.monotonic() - state.last_call_at)
        if wait > 0:
            await asyncio.sleep(wait)
        state.last_call_at = time.monotonic()
    return state


def _release_llm_slot(state: _RateLimitState | None) -> None:
    if state is not None:
        state.gate.release()


def _is_rate_limit_error(exc: BaseException) -> bool:
    from openai import RateLimitError  # type: ignore

    if isinstance(exc, RateLimitError):
        return True
    msg = str(exc).lower()
    return "429" in msg or "rate limit" in msg or "qpm" in msg


def _is_transient_provider_error(exc: BaseException) -> bool:
    """归因等后台任务可安全重试的临时上游错误。"""
    if _is_rate_limit_error(exc) or isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return True
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int) and status_code >= 500:
        return True
    message = str(exc).lower()
    return any(marker in message for marker in (
        "internalservererror", "internal server error", "internal_server_error",
        "bad gateway", "service unavailable", "gateway timeout", "connection error",
        "connection reset", "timed out", "timeout",
    ))


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
        enable_thinking: bool | None = None,
        owner: str = "LLM",
    ):
        self.provider = provider
        self.api_key = api_key
        self.api_key_env = api_key_env
        self.base_url = base_url or None
        self.api_version = api_version
        self.default_headers = default_headers or {}
        self.enable_thinking = enable_thinking
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

        # codex 是本地 Codex 网关的标识；网关提供 OpenAI 兼容的
        # /v1/chat/completions，因此复用同一客户端实现。
        if self.provider in {"openai", "codex"}:
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
        *,
        request_timeout_s: float | None = None,
        retry_transient_errors: bool = False,
        request_headers: dict[str, str] | None = None,
        on_retry: Callable[[int, BaseException, float], Awaitable[None] | None] | None = None,
    ) -> dict[str, Any]:
        """单条 user prompt → 严格 JSON 响应，带限速指数退避。返回 ``json.loads(text)``。

        退避数学复用 ``medeval.retry``（单一真值源）：``min(40, 5*2^attempt + U(0,2))``；
        QPM 限频时单次退避至少 60s。调用前受 ``configure_llm_rate_limit`` 全局限流。
        """
        from openai import RateLimitError  # type: ignore  # noqa: F401 — retryable 类型

        async def _create():
            # Kimi K3 是仅思考模型：DashScope 要求 temperature 固定为 1，
            # 并使用 reasoning_effort 而不是通用的 enable_thinking 开关。评测
            # 使用 high，避免 max 导致单条判分长时间占用 Worker。
            is_kimi_k3 = is_kimi_k3_model(model)
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 1.0 if is_kimi_k3 else temperature,
                "response_format": {"type": "json_object"},
            }
            if is_kimi_k3:
                kwargs["extra_body"] = {"reasoning_effort": "high"}
            elif self.enable_thinking is not None:
                kwargs["extra_body"] = {"enable_thinking": self.enable_thinking}
            request = self._client.chat.completions.create(  # type: ignore[union-attr]
                **kwargs,
                extra_headers=request_headers or None,
            )
            if request_timeout_s is not None:
                return await asyncio.wait_for(request, timeout=request_timeout_s)
            return await request

        async def _on_retry(attempt: int, exc: BaseException, wait: float) -> None:
            log.warning(
                "%s 触发限速 (尝试 %d/%d)，等待 %.1fs 重试%s",
                self.owner,
                attempt + 1,
                max_retries + 1,
                wait,
                " [QPM]" if "qpm" in str(exc).lower() else "",
            )
            if on_retry is not None:
                callback_result = on_retry(attempt, exc, wait)
                if inspect.isawaitable(callback_result):
                    await callback_result

        rate_limit_state = await _acquire_llm_slot()
        try:
            resp = await retry_async(
                _create,
                max_retries=max_retries,
                retryable=_is_transient_provider_error if retry_transient_errors else _is_rate_limit_error,
                base=2.0 if retry_transient_errors else 5.0,
                factor=2.0,
                max_delay=20.0 if retry_transient_errors else 40.0,
                jitter=2.0,
                on_retry=_on_retry,
                delay_for=_delay_for_rate_limit,
            )
        finally:
            _release_llm_slot(rate_limit_state)
        text = resp.choices[0].message.content or "{}"
        return json.loads(text)


def backend_from_llm_cfg(cfg, *, owner: str = "LLM") -> LLMBackend:
    """从八维或指南 Judge 配置构造 LLMBackend。"""
    return LLMBackend(
        provider=cfg.provider,
        api_key=cfg.api_key,
        api_key_env=cfg.api_key_env,
        base_url=cfg.base_url or None,
        api_version=cfg.api_version,
        default_headers=cfg.default_headers,
        enable_thinking=getattr(cfg, "enable_thinking", None),
        owner=owner,
    )
