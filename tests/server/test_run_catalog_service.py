"""runs service：prepare_create_run 等。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from server.schemas import RunCreate


def test_prepare_create_run_duplicate_name_raises(session, settings):
    from server.benchmarks import ensure_builtin_benchmark
    from server.services.runs import prepare_create_run

    bm = ensure_builtin_benchmark(session, settings)
    session.flush()
    existing = RunCreate(benchmark_id=bm.id, run_name="dup-test-run")
    prepare_create_run(session, existing)
    with pytest.raises(HTTPException) as exc:
        prepare_create_run(session, existing)
    assert exc.value.status_code == 409
