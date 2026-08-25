"""Benchmark 库 HTTP 侧：列表/元数据/删除/上传辅助（领域逻辑见 server.benchmarks）。"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

import yaml

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import benchmarks as bm_domain
from ..models_db import Benchmark
from ..schemas import (
    BenchmarkCaseYamlIn,
    BenchmarkCaseYamlOut,
    BenchmarkCaseContentIn,
    BenchmarkCaseContentOut,
    BenchmarkUpdateRequest,
    CaseBrief,
)
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
    bm.mark_updated()
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
            case_type=c.case_type,
            is_bug=c.is_bug,
            level=getattr(c.level, "value", c.level),
        )
        for c in cases
    ]


def _refresh_case_metadata(bm: Benchmark) -> None:
    """单条 Case 写回后同步 Benchmark 列表使用的汇总字段。"""
    cases = bm_domain.load_benchmark_cases(bm)
    bm.case_count = len(cases)
    bm.levels = bm_domain._collect_levels(cases) if cases else []


def get_benchmark_case_yaml(
    session: Session, benchmark_id: int, sample_id: str
) -> BenchmarkCaseYamlOut:
    bm = get_benchmark_or_404(session, benchmark_id)
    try:
        case_file, text = bm_domain.export_case_yaml(bm, sample_id)
    except bm_domain.BenchmarkValidationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return BenchmarkCaseYamlOut(
        benchmark_id=benchmark_id,
        sample_id=sample_id,
        case_file=case_file,
        yaml_text=text,
    )


def save_benchmark_case_yaml(
    session: Session, benchmark_id: int, sample_id: str, payload: BenchmarkCaseYamlIn
) -> BenchmarkCaseYamlOut:
    bm = get_benchmark_or_404(session, benchmark_id)
    try:
        bm_domain.save_case_yaml(bm, sample_id, payload.yaml_text)
    except bm_domain.BenchmarkValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _refresh_case_metadata(bm)
    bm.mark_updated()
    case_file, text = bm_domain.export_case_yaml(bm, sample_id)
    return BenchmarkCaseYamlOut(
        benchmark_id=benchmark_id,
        sample_id=sample_id,
        case_file=case_file,
        yaml_text=text,
    )


def get_benchmark_case_content(
    session: Session, benchmark_id: int, sample_id: str
) -> BenchmarkCaseContentOut:
    """读取单条 Case 的结构化内容，供 UI 分模块编辑而非直接展示 YAML。"""
    bm = get_benchmark_or_404(session, benchmark_id)
    try:
        case_file, text = bm_domain.export_case_yaml(bm, sample_id)
    except bm_domain.BenchmarkValidationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:  # 理论上 export 已保证可解析，仍防御性处理。
        raise HTTPException(status_code=500, detail=f"用例内容解析失败：{exc}") from exc
    if not isinstance(raw, list) or len(raw) != 1 or not isinstance(raw[0], dict):
        raise HTTPException(status_code=500, detail="用例内容格式异常")
    return BenchmarkCaseContentOut(
        benchmark_id=benchmark_id,
        sample_id=sample_id,
        case_file=case_file,
        case=raw[0],
    )


def save_benchmark_case_content(
    session: Session,
    benchmark_id: int,
    sample_id: str,
    payload: BenchmarkCaseContentIn,
) -> BenchmarkCaseContentOut:
    """保存结构化 Case，复用 YAML 保存链路的完整模型校验。"""
    bm = get_benchmark_or_404(session, benchmark_id)
    text = yaml.safe_dump([payload.case], allow_unicode=True, sort_keys=False)
    try:
        bm_domain.save_case_yaml(bm, sample_id, text)
    except bm_domain.BenchmarkValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _refresh_case_metadata(bm)
    bm.mark_updated()
    return get_benchmark_case_content(session, benchmark_id, sample_id)


def delete_benchmark_case(session: Session, benchmark_id: int, sample_id: str) -> None:
    bm = get_benchmark_or_404(session, benchmark_id)
    try:
        cases = bm_domain.delete_case(bm, sample_id)
    except bm_domain.BenchmarkValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    bm.case_count = len(cases)
    bm.tags = []
    bm.levels = bm_domain._collect_levels(cases) if cases else []
    bm.mark_updated()


def export_download(benchmark_id: int, session: Session) -> tuple[str, str]:
    bm = get_benchmark_or_404(session, benchmark_id)
    return bm_domain.export_benchmark_yaml(bm)
