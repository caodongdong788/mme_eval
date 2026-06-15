"""cases 路由：用例库总览（各 benchmark 概览，作为用例浏览入口）。

单个 benchmark 的用例清单见 ``GET /api/benchmarks/{id}/cases``。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..benchmarks import ensure_builtin_benchmark
from ..db import get_session
from ..models_db import Benchmark
from ..schemas import BenchmarkOut

router = APIRouter(prefix="/api/cases", tags=["cases"])


@router.get("", response_model=list[BenchmarkOut])
def list_case_library(session: Session = Depends(get_session)) -> list[Benchmark]:
    ensure_builtin_benchmark(session)
    return list(
        session.execute(select(Benchmark).order_by(Benchmark.id)).scalars().all()
    )
