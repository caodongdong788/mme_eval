"""用例加载器 —— 从 cases/ 目录读取 YAML 并做 Pydantic 校验。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

import yaml

from .models import TestCase

log = logging.getLogger(__name__)


def _deep_merge(base: dict, override: dict) -> dict:
    """深合并两个 mapping，``override`` 优先。

    * dict ∩ dict 递归合并（如 ``evaluation.dimension_criteria``）。
    * 其它类型（含 list）整体被 override 替换——guidelines 等列表不做拼接，
      避免 defaults 的列表悄悄混进逐题集合。
    """
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _expand_items(data: object, path: Path) -> list:
    """把一个 YAML 文档展开成「逐题 dict」列表。

    支持两种顶层形态：
      * **数组**：直接返回各元素。
      * **mapping 且含 ``cases``**：取顶层 ``defaults``（mapping，缺省 {}）逐条
        深合并进 ``cases`` 的每一项（case 侧覆盖 defaults），消除跨题 boilerplate。
    """
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "cases" in data:
        defaults = data.get("defaults") or {}
        if not isinstance(defaults, dict):
            raise ValueError(f"{path}: 顶层 defaults 必须是 mapping")
        cases = data.get("cases")
        if not isinstance(cases, list):
            raise ValueError(f"{path}: 顶层 cases 必须是数组")
        return [
            _deep_merge(defaults, item) if isinstance(item, dict) else item
            for item in cases
        ]
    # 其它单 mapping（无 cases 键）按单题处理，保持旧行为
    return [data]


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
    base_dir: Path | None = None,
) -> list[TestCase]:
    """加载用例。

    Args:
        include: 包含的目录或文件路径（相对 base_dir）。
        exclude: 排除的目录或文件路径。
        base_dir: 解析相对路径用的基准目录。
    """
    base_dir = base_dir or Path.cwd()
    exclude = exclude or []

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

        items = _expand_items(data, path)
        for item in items:
            if not isinstance(item, dict) or item.get("schema_version") != "2.0":
                raise ValueError(
                    f"{path}: 正式 Case 必须声明 schema_version: \"2.0\" 并使用 evaluation"
                )
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
            case = case.model_copy(update={"case_file": path.name})
            cases.append(case)

    log.info("Loaded %d cases", len(cases))
    return cases
