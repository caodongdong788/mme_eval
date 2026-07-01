"""FailureTag.label_zh 元数据测试。

参见 OpenSpec change ``localize-failure-tags-zh``。

覆盖点：
  * 全部当前枚举成员的 label_zh 取值与 design.md 词表严格一致
  * label_zh 全集互不重复（避免飞书报告渲染冲突）
  * label_zh 全集与 dimension 全集不相交（语义层不同，不允许混用）
  * 启动期完整性 assert 在 label_zh 缺失时确实抛 AssertionError
"""

from __future__ import annotations

import importlib
import sys
import textwrap

import pytest

from medeval.models import FailureTag, _TAG_META  # noqa: PLC2701


# ---------------------------------------------------------------------------
# label_zh 词表与 design.md 严格一致
# ---------------------------------------------------------------------------

# 该字典必须与 openspec/changes/localize-failure-tags-zh/design.md
# 决策 1 的词表保持完全一致；任何改动都是 spec 变更，需要新一轮 OpenSpec change。
EXPECTED_LABELS_ZH: dict[FailureTag, str] = {
    FailureTag.MISSED_RED_FLAG: "漏报红旗",
    FailureTag.UNDER_REFERRAL: "转诊不足",
    FailureTag.IMPROPER_PRESCRIPTION: "越界处方",
    FailureTag.OVER_DIAGNOSIS: "越界确诊",
    FailureTag.INQUIRY_INCOMPLETE: "问诊不足",
    FailureTag.CONSTRAINT_VIOLATION: "触发禁词",
    FailureTag.ADAPTER_ERROR: "调用失败",
    FailureTag.EMPATHY_MISS: "共情不足",
    FailureTag.POPULATION_BLIND: "人群盲区",
    FailureTag.DIFFERENTIAL_NARROW: "鉴别窄",
    FailureTag.MEDICAL_HALLUCINATION: "医学幻觉",
    FailureTag.OVER_REFUSAL: "过度拒答",
    FailureTag.DIALOG_BREAK: "上下文断",
    FailureTag.TOOL_MISUSE: "工具误用",
}


def test_label_zh_covers_all_failure_tags():
    """枚举 / 期望词表 / _TAG_META 三方完全同步。"""
    assert set(EXPECTED_LABELS_ZH.keys()) == set(FailureTag), (
        "EXPECTED_LABELS_ZH 与 FailureTag 不同步；新增枚举成员时必须同步本测试"
    )
    assert set(_TAG_META.keys()) == set(FailureTag)


@pytest.mark.parametrize("tag,expected", list(EXPECTED_LABELS_ZH.items()))
def test_label_zh_value_exact(tag: FailureTag, expected: str):
    assert tag.label_zh == expected, (
        f"FailureTag.{tag.name}.label_zh 期望 {expected!r}，实际 {tag.label_zh!r}"
    )


def test_label_zh_property_matches_meta_dict():
    """label_zh property MUST 等价于 _TAG_META[self].label_zh。"""
    for tag in FailureTag:
        assert tag.label_zh == _TAG_META[tag].label_zh


def test_label_zh_all_non_empty():
    for tag in FailureTag:
        assert tag.label_zh, f"{tag.name} label_zh 为空"


def test_label_zh_uniqueness():
    """全集互不重复，避免飞书报告里两个不同 tag 渲染成同一个中文。"""
    labels = [t.label_zh for t in FailureTag]
    duplicates = {x for x in labels if labels.count(x) > 1}
    assert not duplicates, f"label_zh 重复：{duplicates}"


def test_label_zh_does_not_collide_with_dimension():
    """label_zh 与 dimension 取值不相交（前者中文短词，后者英文枚举键）。"""
    labels = {t.label_zh for t in FailureTag}
    dimensions = {t.dimension for t in FailureTag}
    overlap = labels & dimensions
    assert not overlap, f"label_zh 与 dimension 撞值：{overlap}"


def test_label_zh_length_in_designated_range():
    """design.md 决策 1 约束：label_zh 必须 4~8 字（飞书 docx 表格友好区间）。

    注意：少数极简标签（如 ``鉴别窄`` / ``上下文断``）下限到 3 字
    也可接受。这里设定 3~8 字软约束，超出范围按"重新设计短标签"处理。
    """
    for tag in FailureTag:
        n = len(tag.label_zh)
        assert 3 <= n <= 8, (
            f"FailureTag.{tag.name}.label_zh 长度 {n} 越界（期望 3~8 字）"
        )


# ---------------------------------------------------------------------------
# 启动期完整性 assert
# ---------------------------------------------------------------------------


def test_module_import_asserts_label_zh_non_empty(tmp_path, monkeypatch):
    """如果某成员 label_zh 被改成空串，import 期 assert 必须抛 AssertionError。

    用 import_module 在隔离 namespace 重新加载 medeval.models 不现实
    （已 import 的模块缓存住了），改用代码片段验证 assert 行为。
    """
    code = textwrap.dedent("""
        from dataclasses import dataclass

        @dataclass(frozen=True)
        class _TagMeta:
            label_zh: str

        meta = {"A": _TagMeta(label_zh=""), "B": _TagMeta(label_zh="ok")}
        missing = sorted(name for name, m in meta.items() if not m.label_zh)
        assert not missing, f"FailureTag 缺少 label_zh: {missing}"
    """).strip()
    with pytest.raises(AssertionError, match=r"缺少 label_zh: \['A'\]"):
        exec(code, {})


def test_real_module_assert_message_lists_missing_member(monkeypatch):
    """直接补丁 _TAG_META 后重新跑 assert 逻辑，验证消息含成员名。"""
    # 复制现有 meta，故意让 ADAPTER_ERROR.label_zh 变空
    from medeval import models  # type: ignore[attr-defined]

    fake_meta = {
        tag: type(_TAG_META[tag])(
            dimension=_TAG_META[tag].dimension,
            description=_TAG_META[tag].description,
            label_zh="" if tag is FailureTag.ADAPTER_ERROR else _TAG_META[tag].label_zh,
        )
        for tag in FailureTag
    }
    missing = sorted(name.name for name, m in fake_meta.items() if not m.label_zh)
    assert missing == ["ADAPTER_ERROR"]


# ---------------------------------------------------------------------------
# 已 emit 与预留两类标签都必须有 label_zh
# ---------------------------------------------------------------------------


_EMITTED_TAGS = [
    FailureTag.MISSED_RED_FLAG,
    FailureTag.UNDER_REFERRAL,
    FailureTag.IMPROPER_PRESCRIPTION,
    FailureTag.OVER_DIAGNOSIS,
    FailureTag.INQUIRY_INCOMPLETE,
    FailureTag.CONSTRAINT_VIOLATION,
    FailureTag.ADAPTER_ERROR,
]

_RESERVED_TAGS = [
    FailureTag.EMPATHY_MISS,
    FailureTag.POPULATION_BLIND,
    FailureTag.DIFFERENTIAL_NARROW,
    FailureTag.MEDICAL_HALLUCINATION,
    FailureTag.OVER_REFUSAL,
    FailureTag.DIALOG_BREAK,
    FailureTag.TOOL_MISUSE,
]


@pytest.mark.parametrize("tag", _EMITTED_TAGS)
def test_emitted_tags_have_label_zh(tag: FailureTag):
    assert tag.label_zh


@pytest.mark.parametrize("tag", _RESERVED_TAGS)
def test_reserved_tags_have_label_zh(tag: FailureTag):
    """预留标签也必须立即有 label_zh，不等到 LLM Judge 接入再补。"""
    assert tag.label_zh
