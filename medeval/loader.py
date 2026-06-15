"""用例加载器 —— 从 cases/ 目录读取 YAML 并做 Pydantic 校验。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

import yaml

from .models import TestCase

log = logging.getLogger(__name__)


def _iter_yaml_files(roots: Iterable[Path]) -> Iterable[Path]:
    for root in roots:
        if root.is_file() and root.suffix in (".yaml", ".yml"):
            yield root
            continue
        if not root.is_dir():
            continue
        yield from sorted(root.rglob("*.yaml"))
        yield from sorted(root.rglob("*.yml"))


def load_cases(
    include: list[str],
    exclude: list[str] | None = None,
    score_profiles: list[str] | None = None,
    base_dir: Path | None = None,
) -> list[TestCase]:
    """加载用例。

    Args:
        include: 包含的目录或文件路径（相对 base_dir）。
        exclude: 排除的目录或文件路径。
        score_profiles: 只跑这些评分 profile（OR 语义）。空则不过滤。
        base_dir: 解析相对路径用的基准目录。
    """
    base_dir = base_dir or Path.cwd()
    exclude = exclude or []
    score_profiles = score_profiles or []

    include_paths = [base_dir / p for p in include]
    exclude_paths = {(base_dir / p).resolve() for p in exclude}

    cases: list[TestCase] = []
    seen_ids: set[str] = set()

    for path in _iter_yaml_files(include_paths):
        if any(str(path.resolve()).startswith(str(ex)) for ex in exclude_paths):
            continue

        try:
            with path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception as e:
            log.error("Failed to read %s: %s", path, e)
            continue

        if data is None:
            continue

        items = data if isinstance(data, list) else [data]
        for item in items:
            try:
                case = TestCase.model_validate(item)
            except Exception as e:
                log.error("Validation failed for %s: %s", path, e)
                raise
            if case.sample_id in seen_ids:
                raise ValueError(
                    f"Duplicate sample_id '{case.sample_id}' in {path}"
                )
            seen_ids.add(case.sample_id)
            if score_profiles and case.score_profile.value not in score_profiles:
                continue
            case = case.model_copy(update={"case_file": path.name})
            cases.append(case)

    log.info("Loaded %d cases", len(cases))
    return cases
