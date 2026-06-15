"""可选 OpenTelemetry tracing —— 默认 no-op、零开销、不强依赖 otel。

参见 OpenSpec change ``enhance-eval-engine``（借鉴 AgentScope 的 OTel tracing）。

设计约束（与 spec 一致）：
  * **默认关闭**：未调用 ``configure_tracing(enabled=True)`` 时，``span()`` 是零开销空操作。
  * **软依赖**：未安装 ``otel`` 可选依赖时，import 与运行都 MUST 不报错（自动退化为 no-op）。
  * **零侵入**：tracing MUST NOT 改变任何判分结果、评分口径或控制流——只观测。

用法::

    from medeval.observability.tracing import configure_tracing, span
    configure_tracing(enabled=cfg.enabled, endpoint=cfg.endpoint, service_name=cfg.service_name)
    with span("adapter.chat", sample_id="bc_001", turn_index=0) as sp:
        ...
"""

from __future__ import annotations

import contextlib
from typing import Any, Iterator

# 全局 tracer：None = 关闭（no-op）。仅由 configure_tracing / 测试辅助改写。
_tracer: Any = None


def configure_tracing(
    enabled: bool = False,
    endpoint: str = "",
    service_name: str = "medeval",
) -> bool:
    """按需启用 OTel tracing。返回是否真正启用。

    ``enabled=False``（默认）→ 关闭并清空 tracer。``enabled=True`` 但未安装 otel
    或初始化失败 → 静默退化为 no-op 并返回 ``False``（绝不抛错、绝不影响主链路）。
    """
    global _tracer
    if not enabled:
        _tracer = None
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
    except Exception:
        _tracer = None
        return False
    try:
        provider = TracerProvider(
            resource=Resource.create({"service.name": service_name})
        )
        if endpoint:
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            try:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                    OTLPSpanExporter,
                )
            except Exception:
                OTLPSpanExporter = None  # type: ignore[assignment]
            if OTLPSpanExporter is not None:
                provider.add_span_processor(
                    BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
                )
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer("medeval")
        return True
    except Exception:
        _tracer = None
        return False


@contextlib.contextmanager
def span(name: str, **attributes: Any) -> Iterator[Any]:
    """开一个 span 的上下文管理器；tracing 关闭时为零开销 no-op（yield None）。

    ``attributes`` 中值为 None 的键会被跳过；写属性失败被吞掉（绝不影响主链路）。
    """
    tracer = _tracer
    if tracer is None:
        yield None
        return
    with tracer.start_as_current_span(name) as sp:
        _apply_attrs(sp, attributes)
        yield sp


def set_attribute(sp: Any, key: str, value: Any) -> None:
    """安全地给 span 写一个属性（sp 为 None 或写失败时静默忽略）。"""
    if sp is None or value is None:
        return
    try:
        sp.set_attribute(key, value)
    except Exception:
        pass


def _apply_attrs(sp: Any, attributes: dict[str, Any]) -> None:
    for k, v in attributes.items():
        set_attribute(sp, k, v)


# --- 测试辅助（仅供单测注入内存 tracer / 复位状态）--------------------------------


def set_tracer_for_tests(tracer: Any) -> None:
    global _tracer
    _tracer = tracer


def reset_for_tests() -> None:
    global _tracer
    _tracer = None
