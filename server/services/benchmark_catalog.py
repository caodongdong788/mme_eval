"""Benchmark 库 HTTP 侧：列表/元数据/删除/上传辅助（领域逻辑见 server.benchmarks）。"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import benchmarks as bm_domain
from ..models_db import Benchmark
from ..schemas import BenchmarkUpdateRequest, CaseBrief
from ..settings import get_settings


def read_upload_capped(file: UploadFile) -> bytes:
    limit = get_settings().max_upload_bytes
    content = file.file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(
            status_code=413,
            detail=f"上传文件超过大小上限（{limit} 字节）",
        )
    return content


def get_benchmark_or_404(session: Session, benchmark_id: int) -> Benchmark:
    bm = session.get(Benchmark, benchmark_id)
    if bm is None:
        raise HTTPException(status_code=404, detail=f"benchmark {benchmark_id} 不存在")
    return bm


def list_benchmarks(session: Session) -> list[Benchmark]:
    bm_domain.ensure_builtin_benchmark(session)
    return list(
        session.execute(select(Benchmark).order_by(Benchmark.id)).scalars().all()
    )


def update_benchmark(
    session: Session, benchmark_id: int, payload: BenchmarkUpdateRequest
) -> Benchmark:
    bm = get_benchmark_or_404(session, benchmark_id)
    if bm.source == "builtin":
        raise HTTPException(status_code=400, detail="内置 benchmark 不可编辑")
    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="名称不能为空")
        bm.name = name
    if payload.description is not None:
        bm.description = payload.description
    return bm


def delete_benchmark(session: Session, benchmark_id: int) -> None:
    bm = get_benchmark_or_404(session, benchmark_id)
    if bm.source == "builtin":
        raise HTTPException(status_code=400, detail="内置 benchmark 不可删除")
    uploads_root = get_settings().uploads_dir.resolve()
    storage = Path(bm.storage_path).resolve()
    if bm.storage_path and uploads_root in storage.parents:
        shutil.rmtree(storage, ignore_errors=True)
    session.delete(bm)


def list_benchmark_case_briefs(session: Session, benchmark_id: int) -> list[CaseBrief]:
    bm = get_benchmark_or_404(session, benchmark_id)
    cases = bm_domain.load_benchmark_cases(bm)
    return [
        CaseBrief(
            sample_id=c.sample_id,
            scenario=c.scenario,
            sub_scenario=c.sub_scenario,
            level=getattr(c.level, "value", c.level),
            score_profile=getattr(c.score_profile, "value", c.score_profile),
        )
        for c in cases
    ]


def export_download(benchmark_id: int, session: Session) -> tuple[str, str]:
    bm = get_benchmark_or_404(session, benchmark_id)
    return bm_domain.export_benchmark_yaml(bm)
