"""Ray 分布式后端单测（enhance-eval-engine Phase 3）。

覆盖：
  - 默认 local 后端行为不变（run_cases 不传 executor）
  - executor=ray 但未安装 ray → 抛清晰错误，不静默回退
  - ray 路径（local_mode）产物结构与 local 一致：外层=用例、内层=repeat
  - ray worker 在进程内按 adapter_type+config 自建 adapter
"""

from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from medeval.adapter import register_adapter
from medeval.adapter.base import BaseAdapter, ChatRequest, ChatResponse
from medeval.models import Level, TestCase, Turn
from medeval.runner import run_cases


# 注册一个无网络依赖的桩 adapter，供 worker 用 build_adapter 重建。
@register_adapter("ray_stub", config_key="ray_stub")
class _RayStubAdapter(BaseAdapter):
    name = "ray_stub"

    def __init__(self, **kwargs):
        self._kwargs = kwargs

    async def chat(self, req: ChatRequest) -> ChatResponse:
        return ChatResponse(reply="本回答仅供参考", raw={})

    async def close(self) -> None:
        pass


def _case(sid: str, turns: int = 1) -> TestCase:
    return TestCase(
        sample_id=sid,
        scenario="t",
        level=Level.L2,
        turns=[Turn(role="user", content=f"q{i}") for i in range(turns)],
    )


def test_local_backend_default_unchanged():
    cases = [_case("a", 2), _case("b", 1)]
    traces = asyncio.run(
        run_cases(cases, _RayStubAdapter(), concurrency=2, retry=0, repeat=2)
    )
    assert len(traces) == 2
    assert all(len(per_case) == 2 for per_case in traces)  # 内层=repeat


def test_ray_missing_raises_clear_error(monkeypatch):
    """executor=ray 但 import ray 失败 → RuntimeError，不回退 local。"""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "ray" or name.startswith("ray."):
            raise ImportError("no ray")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(RuntimeError, match="ray"):
        asyncio.run(
            run_cases(
                [_case("a")],
                _RayStubAdapter(),
                executor="ray",
                adapter_type="ray_stub",
                adapter_config={"ray_stub": {}},
            )
        )


class _StubHandler(BaseHTTPRequestHandler):
    """返回固定 chat reply 的极简 HTTP 桩（供 ray worker 经 http adapter 命中）。"""

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        payload = json.dumps({"reply": "本回答仅供参考"}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):  # 静默
        pass


def test_ray_backend_structure_matches_local():
    """真实 ray 集群（多进程 worker）下，产物结构与 local 后端一致。

    worker 进程只 import medeval（不 import 本测试模块），故必须用 **内置** http adapter
    （在 worker 的注册表里可见），指向本地桩服务器，验证 worker 内自建 adapter 的完整路径。
    """
    ray = pytest.importorskip("ray")

    server = ThreadingHTTPServer(("127.0.0.1", 0), _StubHandler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    if ray.is_initialized():
        ray.shutdown()
    ray.init(num_cpus=2, ignore_reinit_error=True, include_dashboard=False)
    try:
        cases = [_case("a", 2), _case("b", 1)]
        adapter_config = {
            "http": {
                "base_url": f"http://127.0.0.1:{port}",
                "endpoint": "/chat",
                "response_path": "reply",
            }
        }
        progressed: list[str] = []
        traces = asyncio.run(
            run_cases(
                cases,
                _RayStubAdapter(),  # ray 路径下不参与对话，仅占位
                executor="ray",
                adapter_type="http",
                adapter_config=adapter_config,
                repeat=2,
                on_progress=lambda c, t, i=0: progressed.append(c.sample_id),
            )
        )
        # 外层=用例顺序、内层=repeat，与 local 后端结构一致
        assert [len(p) for p in traces] == [2, 2]
        assert traces[0][0].messages  # 有对话留痕
        assert "本回答仅供参考" in traces[0][0].messages[-1].content
        assert progressed.count("a") == 2 and progressed.count("b") == 2
    finally:
        if ray.is_initialized():
            ray.shutdown()
        server.shutdown()
