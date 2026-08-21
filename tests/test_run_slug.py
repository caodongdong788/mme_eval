"""run_slug —— 输出目录 / report.run_name 自动命名。"""

from __future__ import annotations

from datetime import datetime

from medeval.run_slug import MAX_RUN_SLUG_BYTES, make_run_slug


def test_make_run_slug_includes_local_date_and_ms():
    fixed = datetime(2026, 6, 1, 16, 28, 45, 940000)
    slug = make_run_slug("doubao_breast_cancer", now=fixed)
    assert slug == f"doubao_breast_cancer_2026-06-01_{int(fixed.timestamp() * 1000)}"


def test_make_run_slug_defaults_empty_label():
    fixed = datetime(2026, 6, 1, 12, 0, 0)
    assert make_run_slug("", now=fixed).startswith("default_2026-06-01_")


def test_make_run_slug_bounds_long_unicode_label_for_filesystem(tmp_path):
    fixed = datetime(2026, 8, 21, 3, 36, 0, 741000)
    label = "[REQ] 医带患专家配置与自动化评测" * 30

    slug = make_run_slug(label, now=fixed)

    assert len(slug.encode("utf-8")) <= MAX_RUN_SLUG_BYTES
    assert slug.endswith(f"_2026-08-21_{int(fixed.timestamp() * 1000)}")
    assert slug != make_run_slug(label[:-1], now=fixed)
    # 直接创建运行目录，防止回归到仅按字符数截断而触发 Errno 36。
    (tmp_path / slug).mkdir()
