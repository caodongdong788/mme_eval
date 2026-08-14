"""评测任务的可持久化描述；与具体 JobRunner 解耦。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from .progress import InMemoryProgress

JobFn = Callable[[InMemoryProgress], Awaitable[None]]


@dataclass(frozen=True)
class JobSpec:
    kind: str
    payload: dict[str, Any]


def attach_job_spec(job: JobFn, kind: str, payload: dict[str, Any]) -> JobFn:
    """给进程内闭包附上无密钥任务描述，供数据库调度器序列化。"""
    setattr(job, "__mme_job_spec__", JobSpec(kind=kind, payload=payload))
    return job


def get_job_spec(job: JobFn) -> JobSpec | None:
    value = getattr(job, "__mme_job_spec__", None)
    return value if isinstance(value, JobSpec) else None


def without_api_keys(value: Any) -> Any:
    """递归移除任务参数中的明文密钥，作为写入队列前的最后一道保护。"""
    if isinstance(value, dict):
        return {
            key: without_api_keys(item)
            for key, item in value.items()
            if key not in {"api_key", "token", "secret_key"}
        }
    if isinstance(value, list):
        return [without_api_keys(item) for item in value]
    return value
