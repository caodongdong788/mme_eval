"""benchmark 库测试：合法上传、非法拒绝、builtin 注册、用例解析。"""

from __future__ import annotations

import pytest

from server.benchmarks import (
    BenchmarkValidationError,
    create_uploaded_benchmark,
    ensure_builtin_benchmark,
    export_benchmark_yaml,
    load_benchmark_cases,
    overwrite_benchmark_from_yaml,
    replace_uploaded_benchmark,
)

VALID_YAML = """
- sample_id: up_001
  scenario: 症状
  level: L3
  score_profile: red_flag
  turns:
    - role: user
      content: 我胸口痛
- sample_id: up_002
  scenario: 筛查
  level: L1
  score_profile: knowledge
  turns:
    - role: user
      content: 多久做一次乳腺筛查
""".strip().encode("utf-8")

INVALID_YAML = """
- sample_id: bad_001
  scenario: 缺 level 和 turns 的非法用例
""".strip().encode("utf-8")


def test_upload_valid_benchmark(session, settings):
    bm = create_uploaded_benchmark(
        session, name="我的用例集", content=VALID_YAML, filename="mine.yaml", settings=settings
    )
    session.commit()
    assert bm.id is not None
    assert bm.source == "uploaded"
    assert bm.case_count == 2
    assert set(bm.tags) == {"red_flag", "knowledge"}
    assert set(bm.levels) == {"L1", "L3"}
    # 用例已落到 uploads/<id>/ 且可重新加载
    cases = load_benchmark_cases(bm, settings=settings)
    assert {c.sample_id for c in cases} == {"up_001", "up_002"}


NEW_YAML = (
    "- sample_id: rep_1\n  scenario: s\n  level: L2\n  turns:\n"
    "    - role: user\n      content: hi"
).encode("utf-8")


def test_export_and_replace_benchmark(session, settings):
    bm = create_uploaded_benchmark(
        session, name="原集", content=VALID_YAML, filename="orig.yaml", settings=settings
    )
    session.commit()

    # 下载导出：上传集返回原始内容
    fname, text = export_benchmark_yaml(bm, settings)
    assert "up_001" in text

    # 覆盖重传
    replace_uploaded_benchmark(session, bm, content=NEW_YAML, filename="new.yaml", settings=settings)
    session.commit()
    assert bm.case_count == 1
    assert bm.levels == ["L2"]
    cases = load_benchmark_cases(bm, settings=settings)
    assert {c.sample_id for c in cases} == {"rep_1"}


def test_replace_builtin_rejected(session, settings):
    bm = ensure_builtin_benchmark(session, settings)
    session.commit()
    with pytest.raises(BenchmarkValidationError):
        replace_uploaded_benchmark(session, bm, content=NEW_YAML, settings=settings)


def test_duplicate_name_rejected(session, settings):
    create_uploaded_benchmark(session, name="重名集", content=VALID_YAML, settings=settings)
    session.commit()
    with pytest.raises(BenchmarkValidationError):
        create_uploaded_benchmark(session, name="重名集", content=VALID_YAML, settings=settings)


def test_upload_invalid_benchmark_rejected(session, settings):
    with pytest.raises(BenchmarkValidationError):
        create_uploaded_benchmark(
            session, name="坏的", content=INVALID_YAML, settings=settings
        )


def test_upload_non_utf8_rejected(session, settings):
    with pytest.raises(BenchmarkValidationError):
        create_uploaded_benchmark(
            session, name="二进制", content=b"\xff\xfe\x00bad", settings=settings
        )


# 覆盖保存：仅编辑 up_001 判据，YAML 只含 up_001（模拟过滤子集编辑）
OVERWRITE_YAML = (
    "- sample_id: up_001\n"
    "  expected_behavior:\n"
    "    must_have:\n"
    "      - keyword: 新要点\n"
)


def test_overwrite_yaml_updates_in_place(session, settings):
    bm = create_uploaded_benchmark(
        session, name="待覆盖集", content=VALID_YAML, filename="o.yaml", settings=settings
    )
    session.commit()
    bid = bm.id

    overwrite_benchmark_from_yaml(session, bm, yaml_text=OVERWRITE_YAML, settings=settings)
    session.commit()

    # 同一 benchmark（id 不变）、未编辑的 up_002 原样保留、总数不变
    assert bm.id == bid
    assert bm.source == "uploaded"
    cases = {c.sample_id: c for c in load_benchmark_cases(bm, settings=settings)}
    assert set(cases) == {"up_001", "up_002"}
    # up_001 判据被更新
    kws = [p.keyword for p in cases["up_001"].expected_behavior.must_have]
    assert "新要点" in kws


def test_overwrite_yaml_builtin_rejected(session, settings):
    bm = ensure_builtin_benchmark(session, settings)
    session.commit()
    with pytest.raises(BenchmarkValidationError):
        overwrite_benchmark_from_yaml(session, bm, yaml_text=OVERWRITE_YAML, settings=settings)


def test_overwrite_yaml_zero_match_rejected(session, settings):
    bm = create_uploaded_benchmark(
        session, name="零匹配集", content=VALID_YAML, filename="z.yaml", settings=settings
    )
    session.commit()
    bad = "- sample_id: not_exist\n  expected_behavior:\n    must_have:\n      - keyword: x\n"
    with pytest.raises(BenchmarkValidationError):
        overwrite_benchmark_from_yaml(session, bm, yaml_text=bad, settings=settings)


def test_ensure_builtin_idempotent(session, settings):
    first = ensure_builtin_benchmark(session, settings)
    session.commit()
    assert first is not None
    assert first.source == "builtin"
    assert first.case_count > 0
    # 再次调用不重复创建
    second = ensure_builtin_benchmark(session, settings)
    assert second.id == first.id


def test_ensure_builtin_refreshes_case_count(session, settings):
    bm = ensure_builtin_benchmark(session, settings)
    assert bm is not None
    bm.case_count = 71
    session.flush()
    refreshed = ensure_builtin_benchmark(session, settings)
    cases = load_benchmark_cases(bm, settings=settings)
    assert refreshed.case_count == len(cases)
    assert refreshed.case_count != 71
