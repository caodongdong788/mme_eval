"""Test markdown report appends transcripts URL footer."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from medeval.models import (
    CaseResult,
    ChatMessage,
    ConversationTrace,
    Level,
    RunReport,
    TestCase,
    Turn,
)
from medeval.reporter.markdown_report import render_markdown


def _empty_report() -> RunReport:
    return RunReport(run_name="t", results=[], total=0, n_runs=1)


def test_no_transcripts_url_no_footer():
    md = render_markdown(_empty_report())
    assert "完整对话流水" not in md


def test_https_transcripts_url_appears_in_footer():
    md = render_markdown(_empty_report(), transcripts_url="https://feishu/x")
    assert md.rstrip().endswith("**完整对话流水**：https://feishu/x")


def test_local_path_fallback():
    md = render_markdown(_empty_report(), transcripts_url="outputs/run/transcripts.xlsx")
    assert "**完整对话流水**：outputs/run/transcripts.xlsx" in md
