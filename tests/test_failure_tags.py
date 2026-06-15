"""FailureTag 词表自检 —— 强制每个成员都有元数据，并验证 Pydantic 校验。"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from medeval.models import FailureTag, TestCase, _TAG_META, _TAG_META as _META_DICT  # noqa: PLC2701


_ALLOWED_DIMENSIONS = {"red_flag", "prescription", "compliance", "communication", "system"}


def test_every_member_has_meta():
    """每个 FailureTag 成员必须在 _TAG_META 中有完整元数据。"""
    for tag in FailureTag:
        assert tag in _META_DICT, f"FailureTag.{tag.name} 缺少 _TAG_META 条目"
        meta = _META_DICT[tag]
        assert meta.dimension in _ALLOWED_DIMENSIONS, (
            f"{tag.name} 的 dimension={meta.dimension!r} 不在白名单内"
        )
        assert meta.description, f"{tag.name} 的 description 为空"
        assert len(meta.description) <= 80, (
            f"{tag.name} 的 description 超过 80 字符限制：{len(meta.description)}"
        )


def test_property_access():
    """FailureTag.X.dimension / .description 必须可访问。"""
    tag = FailureTag.MISSED_RED_FLAG
    assert tag.dimension == "red_flag"
    assert "红旗" in tag.description


def test_str_value_compatibility():
    """FailureTag 作为 str 子类，与字符串比较和 json 序列化必须等价。"""
    assert FailureTag.MISSED_RED_FLAG == "missed_red_flag"
    assert FailureTag.MISSED_RED_FLAG.value == "missed_red_flag"
    # json.dumps 必须输出纯字符串
    encoded = json.dumps([FailureTag.MISSED_RED_FLAG, FailureTag.OVER_DIAGNOSIS])
    assert encoded == '["missed_red_flag", "over_diagnosis"]'


def test_testcase_accepts_valid_candidates():
    case = TestCase(
        sample_id="t1",
        scenario="测试",
        level="L1",
        turns=[{"role": "user", "content": "hi"}],
        failure_tags_candidates=["missed_red_flag", "over_diagnosis"],
    )
    assert case.failure_tags_candidates == [
        FailureTag.MISSED_RED_FLAG,
        FailureTag.OVER_DIAGNOSIS,
    ]


def test_testcase_rejects_unknown_candidate():
    with pytest.raises(ValidationError) as exc_info:
        TestCase(
            sample_id="t2",
            scenario="测试",
            level="L1",
            turns=[{"role": "user", "content": "hi"}],
            failure_tags_candidates=["prompt_injection_success"],
        )
    msg = str(exc_info.value)
    assert "failure_tags_candidates" in msg
    assert "prompt_injection_success" in msg


def test_testcase_default_is_empty_list():
    case = TestCase(
        sample_id="t3",
        scenario="测试",
        level="L1",
        turns=[{"role": "user", "content": "hi"}],
    )
    assert case.failure_tags_candidates == []


def test_emit_categories_present():
    """已 emit 的 8 个标签必须都存在（防回退）。"""
    expected_emit = {
        "missed_red_flag",
        "under_referral",
        "improper_prescription",
        "over_diagnosis",
        "disclaimer_miss",
        "inquiry_incomplete",
        "constraint_violation",
        "adapter_error",
    }
    actual = {t.value for t in FailureTag}
    assert expected_emit <= actual, f"丢失已 emit 的标签：{expected_emit - actual}"


def test_reserved_members_present():
    """README 与用例已引用的 7 个预留标签必须存在。"""
    expected_reserved = {
        "empathy_miss",
        "population_blind",
        "differential_narrow",
        "medical_hallucination",
        "over_refusal",
        "dialog_break",
        "tool_misuse",
    }
    actual = {t.value for t in FailureTag}
    assert expected_reserved <= actual


def test_readme_in_sync_with_enum():
    """README 失败归因标签段必须与 FailureTag 词表同步（CI 防漂移）。"""
    from medeval.docs.gen_failure_tags import check
    from pathlib import Path

    rc = check(Path(__file__).resolve().parent.parent / "README.md")
    assert rc == 0, "README 与 FailureTag 不一致，请运行 python -m medeval.docs.gen_failure_tags --write"
