"""LLMJudge prompt 多轮渲染单测。

确保 ``_PROMPT_TEMPLATE`` 与 ``_format_conversation`` 满足
``judging-pipeline`` spec 中"LLMJudge 必须以完整对话历史为判分输入"约束的所有场景：

  * 多轮用例的对话整段进入 prompt（含 turn 编号递增）
  * 单轮用例向后兼容
  * 预设 system turn 显式标注但不计入 turn 编号
  * prompt 模板字面量变化必须改变 fingerprint（由 test_judge_fingerprint 守护）
"""

from __future__ import annotations

from medeval.judges.llm import _PROMPT_TEMPLATE, _format_conversation
from medeval.models import ChatMessage, ConversationTrace


def _trace(*pairs: tuple[str, str]) -> ConversationTrace:
    return ConversationTrace(
        messages=[ChatMessage(role=role, content=content) for role, content in pairs]
    )


def test_two_turn_conversation_renders_in_order():
    trace = _trace(
        ("user", "我胸口闷"),
        ("assistant", "能描述一下疼痛性质吗"),
        ("user", "持续 1 小时左肩放射出冷汗"),
        ("assistant", "立即拨打 120"),
    )
    out = _format_conversation(trace)
    lines = out.splitlines()
    assert lines == [
        "[turn 1 · 用户] 我胸口闷",
        "[turn 1 · bot] 能描述一下疼痛性质吗",
        "[turn 2 · 用户] 持续 1 小时左肩放射出冷汗",
        "[turn 2 · bot] 立即拨打 120",
    ]


def test_three_turn_conversation_increments_turn_index():
    trace = _trace(
        ("user", "我头痛"),
        ("assistant", "请问诱因和时长？"),
        ("user", "熬夜后开始，3 天了"),
        ("assistant", "建议规律作息，必要时就医。"),
        ("user", "对了我怀孕 18 周"),
        ("assistant", "孕期慎用药，建议产科面诊"),
    )
    out = _format_conversation(trace)
    assert "[turn 1 · 用户] 我头痛" in out
    assert "[turn 2 · 用户] 熬夜后开始，3 天了" in out
    assert "[turn 3 · 用户] 对了我怀孕 18 周" in out
    assert "[turn 3 · bot] 孕期慎用药，建议产科面诊" in out
    assert "用户最近输入" not in out  # 旧字段必须消失


def test_five_turn_conversation_ordering():
    pairs: list[tuple[str, str]] = []
    for i in range(1, 6):
        pairs.append(("user", f"用户第{i}问"))
        pairs.append(("assistant", f"bot第{i}答"))
    out = _format_conversation(_trace(*pairs))
    lines = out.splitlines()
    assert len(lines) == 10
    for i in range(1, 6):
        assert f"[turn {i} · 用户] 用户第{i}问" in lines
        assert f"[turn {i} · bot] bot第{i}答" in lines


def test_system_turn_rendered_separately_and_excluded_from_index():
    trace = _trace(
        ("system", "你是儿科医生"),
        ("user", "孩子发烧 39"),
        ("assistant", "几岁的孩子？"),
        ("user", "10 个月"),
        ("assistant", "婴儿发烧请尽快就医。"),
    )
    out = _format_conversation(trace)
    lines = out.splitlines()
    assert lines[0] == "[系统提示] 你是儿科医生"
    assert lines[1] == "[turn 1 · 用户] 孩子发烧 39"
    assert lines[2] == "[turn 1 · bot] 几岁的孩子？"
    assert lines[3] == "[turn 2 · 用户] 10 个月"
    assert lines[4] == "[turn 2 · bot] 婴儿发烧请尽快就医。"
    assert "[turn 0" not in out


def test_single_turn_backward_compat():
    trace = _trace(
        ("user", "成年人体温多少度算发烧？"),
        ("assistant", "腋下 37.5°C 以上属低热"),
    )
    out = _format_conversation(trace)
    assert "[turn 1 · 用户] 成年人体温多少度算发烧？" in out
    assert "[turn 1 · bot] 腋下 37.5°C 以上属低热" in out
    assert out.count("[turn 1 ·") == 2


def test_prompt_template_uses_conversation_placeholder():
    rendered = _PROMPT_TEMPLATE.format(
        conversation="[turn 1 · 用户] x\n[turn 1 · bot] y",
        rubric_text="- empathy (0~2)",
    )
    assert "【完整对话历史" in rendered
    assert "[turn 1 · 用户] x" in rendered
    assert "[turn 1 · bot] y" in rendered
    assert "multi_turn_consistency" in rendered
    assert "{user}" not in rendered and "{reply}" not in rendered
