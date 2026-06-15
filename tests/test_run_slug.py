"""run_slug —— 输出目录 / report.run_name 自动命名。"""

from __future__ import annotations

from datetime import datetime

from medeval.run_slug import make_run_slug


def test_make_run_slug_includes_local_date_and_ms():
    fixed = datetime(2026, 6, 1, 16, 28, 45, 940000)
    slug = make_run_slug("doubao_breast_cancer", now=fixed)
    assert slug == f"doubao_breast_cancer_2026-06-01_{int(fixed.timestamp() * 1000)}"


def test_make_run_slug_defaults_empty_label():
    fixed = datetime(2026, 6, 1, 12, 0, 0)
    assert make_run_slug("", now=fixed).startswith("default_2026-06-01_")
