"""validate_judge_prompt_template 单元测试。"""

from __future__ import annotations

import pytest

from medeval.judges.prompt_template import (
    DEFAULT_PROMPT_TEMPLATE,
    validate_judge_prompt_template,
)


def test_default_template_passes():
    validate_judge_prompt_template(DEFAULT_PROMPT_TEMPLATE)


def test_missing_placeholder_rejected():
    with pytest.raises(ValueError, match="缺少占位符"):
        validate_judge_prompt_template("only {conversation} scores reasons flags")


def test_unescaped_brace_rejected():
    bad = (
        "x {conversation} {rubric_text} {tool_context} "
        '{"scores": {}} scores reasons flags'
    )
    with pytest.raises(ValueError, match="花括号"):
        validate_judge_prompt_template(bad)


def test_missing_json_fields_rejected():
    t = "ok {conversation} {rubric_text} {tool_context} scores reasons"
    with pytest.raises(ValueError, match="flags"):
        validate_judge_prompt_template(t)
