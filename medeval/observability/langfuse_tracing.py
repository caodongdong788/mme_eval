"""可选 Langfuse 追踪 —— 仅追踪被测 bot，默认 no-op、零开销、软依赖。

参见 OpenSpec change ``add-langfuse-bot-tracing``。

设计约束（与 spec 一致，照搬 ``observability/tracing.py`` 的口径）：
  * **默认关闭**：未调用 ``configure_langfuse(enabled=True)`` 时，所有追踪 API 是零开销 no-op。
  * **软依赖**：未安装 ``langfuse`` 可选依赖时，import 与运行都 MUST NOT 报错（自动退化 no-op）。
  * **零侵入**：追踪 MUST NOT 改变任何判分结果、评分口径或控制流——只观测；内部异常一律静默吞掉。
  * **bot-only**：只在 runner 的 adapter 调用处埋点；judge 的 LLM 调用不追踪。

三级结构：run 级 root span（``run_name``）→ 每条 case/run 会话 span → 每个 user turn generation。

用法::

    from medeval.observability import langfuse_tracing as lf
    lf.configure_langfuse(enabled=cfg.enabled, host=cfg.host, public_key=..., secret_key=...)
    with lf.conversation("conversation", sample_id="bc_001", run_idx=0):
        with lf.generation("adapter.chat", input=messages, model="gpt-4o") as gen:
            resp = await adapter.chat(req)
            lf.update_generation(gen, output=resp.reply, usage=usage, latency_ms=12.3)
    lf.flush()
"""

from __future__ import annotations

import contextlib
import logging
import os
from typing import Any, Iterator

logger = logging.getLogger(__name__)

# 全局 Langfuse client：None = 关闭（no-op）。仅由 configure_langfuse / 测试辅助改写。
_client: Any = None


def configure_langfuse(
    enabled: bool = False,
    host: str = "",
    public_key: str = "",
    secret_key: str = "",
    sample_rate: float = 1.0,
    debug: bool = False,
) -> bool:
    """按需启用 Langfuse 追踪。返回是否真正启用。

    ``enabled=False``（默认）→ 关闭并清空 client。``enabled=True`` 但未安装 langfuse、
    缺少凭据或初始化失败 → 静默退化为 no-op 并返回 ``False``（绝不抛错、绝不影响主链路）。
    """
    global _client
    if not enabled:
        _client = None
        return False
    try:
        from langfuse import Langfuse  # type: ignore
    except Exception:
        logger.debug("langfuse 未安装或 import 失败，追踪退化为 no-op", exc_info=True)
        _client = None
        return False
    try:
        kwargs: dict[str, Any] = {"sample_rate": sample_rate}
        if host:
            kwargs["host"] = host
        if public_key:
            kwargs["public_key"] = public_key
        if secret_key:
            kwargs["secret_key"] = secret_key
        if debug:
            kwargs["debug"] = True
        _client = Langfuse(**kwargs)
        return True
    except Exception:
        logger.debug("Langfuse client 初始化失败，追踪退化为 no-op", exc_info=True)
        _client = None
        return False


def configure_from_env(cfg: Any) -> bool:
    """便捷入口：从 ``LangfuseCfg`` + 环境变量读取凭据并启用。

    ``cfg`` 形如 ``config.observability.langfuse``（含 enabled/host/public_key_env/
    secret_key_env/sample_rate/debug）。凭据只从环境变量读，绝不落配置快照。
    """
    try:
        if not getattr(cfg, "enabled", False):
            _client_off()
            return False
        # 自托管地址优先级：config.host > LANGFUSE_HOST > LANGFUSE_BASE_URL > 留空（SDK 默认）。
        host = (
            (getattr(cfg, "host", "") or "")
            or os.environ.get("LANGFUSE_HOST", "")
            or os.environ.get("LANGFUSE_BASE_URL", "")
        )
        return configure_langfuse(
            enabled=True,
            host=host,
            public_key=os.environ.get(getattr(cfg, "public_key_env", "") or "", ""),
            secret_key=os.environ.get(getattr(cfg, "secret_key_env", "") or "", ""),
            sample_rate=getattr(cfg, "sample_rate", 1.0),
            debug=getattr(cfg, "debug", False),
        )
    except Exception:
        logger.debug("从环境配置 Langfuse 失败，追踪退化为 no-op", exc_info=True)
        _client_off()
        return False


def _client_off() -> None:
    global _client
    _client = None


@contextlib.contextmanager
def conversation(
    name: str, *, session_id: str | None = None, **attributes: Any
) -> Iterator[Any]:
    """会话级 span；作为一条**独立 trace** 的根（一条 case/run 一个）。

    ``session_id`` 给定时把它设到 trace 上（如 ``run_name``），使同一 run 的所有用例
    在 Langfuse 归入同一 session 可整体回放。追踪关闭时为零开销 no-op（yield None）。
    """
    with _observation(name, as_type="span", metadata=attributes) as obs:
        if obs is not None and session_id:
            try:
                obs.update_trace(session_id=session_id)
            except Exception:
                pass
        yield obs


def current_trace_id() -> str | None:
    """当前活跃 trace 的 id；追踪关闭/无活跃 trace/失败时返回 None。"""
    client = _client
    if client is None:
        return None
    try:
        return client.get_current_trace_id()
    except Exception:
        return None


def trace_url(trace_id: str | None) -> str | None:
    """据 trace_id 生成自托管 Langfuse 深链（SDK 自动带 project_id + base_url）。

    追踪关闭、trace_id 为空或失败时返回 None（best-effort、绝不抛错）。
    """
    client = _client
    if client is None or not trace_id:
        return None
    try:
        return client.get_trace_url(trace_id=trace_id)
    except Exception:
        return None


@contextlib.contextmanager
def root_span(name: str, **attributes: Any) -> Iterator[Any]:
    """run 级 root span（trace 名取 ``name``，如 run_name）；关闭时 no-op。"""
    with _observation(name, as_type="span", metadata=attributes) as obs:
        yield obs


@contextlib.contextmanager
def generation(
    name: str,
    *,
    input: Any = None,
    model: str | None = None,
    **attributes: Any,
) -> Iterator[Any]:
    """单个 user turn 的 bot 调用 generation；关闭时 no-op（yield None）。

    返回的 handle 供 ``update_generation`` 回填 output/usage/latency。
    """
    with _observation(
        name, as_type="generation", input=input, model=model, metadata=attributes
    ) as obs:
        yield obs


def update_generation(
    handle: Any,
    *,
    output: Any = None,
    usage: dict[str, int] | None = None,
    latency_ms: float | None = None,
    error: str | None = None,
) -> None:
    """给 generation handle 回填结果；handle 为 None 或写失败时静默忽略。"""
    if handle is None:
        return
    try:
        kwargs: dict[str, Any] = {}
        if output is not None:
            kwargs["output"] = output
        if usage:
            kwargs["usage_details"] = usage
        meta: dict[str, Any] = {}
        if latency_ms is not None:
            meta["latency_ms"] = latency_ms
        if error is not None:
            meta["error"] = error
        if meta:
            kwargs["metadata"] = meta
        if kwargs:
            handle.update(**kwargs)
    except Exception:
        pass


def flush() -> None:
    """落盘缓冲的 trace（短命 CLI 进程收尾必调）；关闭/失败时静默忽略。"""
    client = _client
    if client is None:
        return
    try:
        client.flush()
    except Exception:
        pass


def shutdown() -> None:
    """关停 client 并 flush；关闭/失败时静默忽略。"""
    client = _client
    if client is None:
        return
    try:
        client.shutdown()
    except Exception:
        pass


# --- 内部：统一的 observation 上下文（创建失败 → 退化 no-op，绝不让追踪异常逃逸）-------


@contextlib.contextmanager
def _observation(
    name: str,
    *,
    as_type: str,
    input: Any = None,
    model: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Iterator[Any]:
    client = _client
    if client is None:
        yield None
        return
    kwargs: dict[str, Any] = {"as_type": as_type, "name": name}
    if input is not None:
        kwargs["input"] = input
    if model is not None:
        kwargs["model"] = model
    clean_meta = {k: v for k, v in (metadata or {}).items() if v is not None}
    if clean_meta:
        kwargs["metadata"] = clean_meta
    try:
        cm = client.start_as_current_observation(**kwargs)
    except Exception:
        yield None
        return
    # 进入/退出 observation 上下文：用户代码体（yield 之后）的异常 MUST 原样抛出，
    # 仅吞掉追踪自身（__enter__/__exit__）的异常。
    try:
        obs = cm.__enter__()
    except Exception:
        yield None
        return
    body_failed = False
    try:
        yield obs
    except BaseException:
        body_failed = True
        try:
            cm.__exit__(*__import__("sys").exc_info())
        except Exception:
            pass
        raise
    finally:
        if not body_failed:
            try:
                cm.__exit__(None, None, None)
            except Exception:
                pass


# --- 测试辅助（仅供单测注入 fake client / 复位状态）--------------------------------


def set_client_for_tests(client: Any) -> None:
    global _client
    _client = client


def reset_for_tests() -> None:
    global _client
    _client = None
