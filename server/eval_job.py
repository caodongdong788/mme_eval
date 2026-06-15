"""评测任务门面：re-export 公开 API 与测试 monkeypatch 锚点。

实现位于 ``server.services.eval_*``；子模块在运行时通过本门面解析
``evaluate`` / ``judge_traces`` 等，便于测试 ``monkeypatch.setattr("server.eval_job.*")``。
"""

from __future__ import annotations

from medeval import retention
from medeval.adapter import build_adapter
from medeval.service import evaluate, judge_traces

from .benchmarks import load_benchmark_cases
from .services.eval_artifacts import persist_outcome as _persist_outcome
from .services.eval_launch import build_eval_job
from .services.eval_rejudge import build_rejudge_job, preview_rejudge_case
from .services.eval_release_thresholds import (
    apply_release_threshold_overrides,
    load_release_threshold_overrides,
)
from .services.eval_resume import build_resume_job

__all__ = [
    "apply_release_threshold_overrides",
    "build_adapter",
    "build_eval_job",
    "build_rejudge_job",
    "build_resume_job",
    "evaluate",
    "judge_traces",
    "load_benchmark_cases",
    "load_release_threshold_overrides",
    "preview_rejudge_case",
    "retention",
    "_persist_outcome",
]
