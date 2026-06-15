"""可观测性（observability）：可选 OpenTelemetry tracing。

参见 OpenSpec change ``enhance-eval-engine``。默认 no-op、零开销；未安装 ``otel``
可选依赖或未显式开启时绝不影响主链路。
"""

from .tracing import configure_tracing, span

__all__ = ["configure_tracing", "span"]
