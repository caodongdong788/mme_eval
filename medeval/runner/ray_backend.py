"""Ray 分布式执行后端（参见 OpenSpec change ``enhance-eval-engine``）。

借鉴 AgentScope ``RayEvaluator`` 的分布式评测思路：把每条用例（含 N-runs）作为一个
Ray task 分发到多 worker 并行执行。关键约束：

  * **worker 内自建 adapter**：持有 httpx client 的 adapter 不可跨进程序列化，故只把
    adapter 的 ``type`` + 配置 dict 传进 worker，由 worker 用 ``build_adapter`` 重建实例。
  * **产物结构对齐 local 后端**：返回 ``list[list[ConversationTrace]]``（外层=用例、
    内层=repeat），使后续 ``fold_n_runs`` / judging / ``build_report`` 完全不变。
  * **跨进程传输用 dict**：``TestCase`` / ``ConversationTrace`` 以 ``model_dump`` 往返，
    规避 pydantic 跨版本 pickle 的边角问题。

ray 为可选依赖（``medeval[ray]``）；未安装时本模块的入口会抛出清晰错误，**绝不静默回退**。
"""

from __future__ import annotations

import asyncio
from typing import Any, Sequence

from ..models import ConversationTrace, TestCase


def _run_case_worker(
    case_dict: dict,
    adapter_type: str,
    adapter_config: dict,
    timeout_s: float,
    retry: int,
    repeat: int,
    backoff_base_s: float,
    backoff_max_s: float,
) -> list[dict]:
    """在 worker 进程内跑一条用例的全部 N-runs，返回 trace 的 dict 列表。

    与本地后端逐 run 顺序执行的口径一致（保证 stability 语义不变）。
    """
    from ..adapter import build_adapter
    from .executor import _run_one

    case = TestCase.model_validate(case_dict)

    async def _go() -> list[dict]:
        adapter = build_adapter(adapter_type, adapter_config)
        out: list[dict] = []
        try:
            for run_idx in range(repeat):
                suffix = f"#run{run_idx}" if repeat > 1 else ""
                tr = await _run_one(
                    case,
                    adapter,
                    timeout_s,
                    retry,
                    suffix,
                    backoff_base_s=backoff_base_s,
                    backoff_max_s=backoff_max_s,
                )
                out.append(tr.model_dump(mode="json"))
        finally:
            await adapter.close()
        return out

    return asyncio.run(_go())


def run_cases_ray(
    cases: Sequence[TestCase],
    adapter_type: str,
    adapter_config: dict[str, Any],
    *,
    timeout_s: float = 60,
    retry: int = 2,
    repeat: int = 1,
    on_progress=None,
    retry_backoff_base_s: float = 0.0,
    retry_backoff_max_s: float = 40.0,
    ray_address: str = "",
    ray_num_workers: int = 0,
) -> list[list[ConversationTrace]]:
    """用 Ray 分布式执行全部用例，返回与本地后端结构一致的二维 trace 列表。

    未安装 ray 时抛出清晰 ``RuntimeError``（不回退 local）。
    """
    try:
        import ray
    except ImportError as e:  # pragma: no cover - 取决于环境是否装 ray
        raise RuntimeError(
            "run.executor=ray 需要安装可选依赖：pip install 'medeval[ray]'。"
            "（不会静默回退到 local 后端。）"
        ) from e

    init_kwargs: dict[str, Any] = {"ignore_reinit_error": True}
    if ray_address:
        init_kwargs["address"] = ray_address
    if ray_num_workers > 0:
        init_kwargs["num_cpus"] = ray_num_workers
    started_here = not ray.is_initialized()
    if started_here:
        ray.init(**init_kwargs)

    remote_fn = ray.remote(_run_case_worker)
    try:
        futures = [
            remote_fn.remote(
                case.model_dump(mode="json"),
                adapter_type,
                adapter_config,
                timeout_s,
                retry,
                repeat,
                retry_backoff_base_s,
                retry_backoff_max_s,
            )
            for case in cases
        ]
        results: list[list[ConversationTrace]] = []
        for i, fut in enumerate(futures):
            trace_dicts = ray.get(fut)
            traces = [ConversationTrace.model_validate(d) for d in trace_dicts]
            results.append(traces)
            if on_progress:
                for run_idx, tr in enumerate(traces):
                    try:
                        on_progress(cases[i], tr, run_idx)
                    except TypeError:
                        on_progress(cases[i], tr)
        return results
    finally:
        if started_here:
            ray.shutdown()
