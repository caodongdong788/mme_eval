"""用例加载器 —— 从 cases/ 目录读取 YAML 并做 Pydantic 校验。"""

from __future__ import annotations

import base64
import logging
import mimetypes
import re
from pathlib import Path
from typing import Iterable

import yaml

from .models import TestCase

log = logging.getLogger(__name__)

_SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
_MAX_IMAGE_BYTES = 10 * 1024 * 1024
_MARKDOWN_IMAGE_PATH_RE = re.compile(r"!\[[^\]]*\]\(\s*(images/[^\s)]+)", re.IGNORECASE)


def _image_data_url(raw_path: str, *, yaml_dir: Path) -> str:
    """将 ZIP benchmark 中的相对图片路径解析为受控 data URL。"""
    relative = Path(raw_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"图片路径必须位于用例包内：{raw_path}")
    if not relative.parts or relative.parts[0] != "images":
        raise ValueError(f"图片必须放在 images/ 目录：{raw_path}")
    if relative.suffix.lower() not in _SUPPORTED_IMAGE_SUFFIXES:
        raise ValueError(f"不支持的图片格式：{raw_path}")
    image_path = (yaml_dir / relative).resolve()
    root = yaml_dir.resolve()
    if root not in image_path.parents or not image_path.is_file():
        raise ValueError(f"未找到图片文件：{raw_path}")
    size = image_path.stat().st_size
    if size > _MAX_IMAGE_BYTES:
        raise ValueError(f"图片超过 10 MiB 限制：{raw_path}")
    mime = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
    return f"data:{mime};base64,{base64.b64encode(image_path.read_bytes()).decode('ascii')}"


def _hydrate_case_images(case: TestCase, *, yaml_dir: Path) -> TestCase:
    """为 Case 的每个 turn 注入运行时图片内容，序列化时不带出 base64。

    图片既可以显式声明在 ``turn.images``，也可以写在用户内容的 Markdown 图片
    ``![说明](images/xxx.jpg)`` 中，后者兼容已有的 benchmark 编辑方式。
    """
    dynamic_turns = []
    if case.conversation is not None:
        dynamic_turns = [
            case.conversation.opening,
            *[rule.reply for rule in case.conversation.reply_rules],
            *case.conversation.follow_ups,
        ]
    for turn in [*case.turns, *dynamic_turns]:
        markdown_paths = _MARKDOWN_IMAGE_PATH_RE.findall(turn.content)
        image_paths = list(dict.fromkeys([*turn.images, *markdown_paths]))
        if image_paths:
            turn.attach_image_data_urls(
                [_image_data_url(raw_path, yaml_dir=yaml_dir) for raw_path in image_paths]
            )
    return case


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
        return [_normalize_case_initial_state(item) for item in data]
    if isinstance(data, dict) and "cases" in data:
        defaults = data.get("defaults") or {}
        if not isinstance(defaults, dict):
            raise ValueError(f"{path}: 顶层 defaults 必须是 mapping")
        cases = data.get("cases")
        if not isinstance(cases, list):
            raise ValueError(f"{path}: 顶层 cases 必须是数组")
        return [
            _normalize_case_initial_state(_deep_merge(defaults, item))
            if isinstance(item, dict)
            else item
            for item in cases
        ]
    # 其它单 mapping（无 cases 键）按单题处理，保持旧行为
    return [_normalize_case_initial_state(data)]


def _normalize_case_initial_state(item: object) -> object:
    """将顶层 ``user_profile`` 归一到 ``initial_state.user_profile``。

    用户画像是自由键值结构，Case 不再改写其中的字段；显式的
    ``initial_state.user_profile`` 在同名字段上优先。
    """
    if not isinstance(item, dict):
        return item

    normalized = dict(item)
    legacy_profile = normalized.pop("user_profile", None)
    if legacy_profile is not None and not isinstance(legacy_profile, dict):
        return normalized
    initial_state = normalized.get("initial_state") or {}
    if not isinstance(initial_state, dict):
        return normalized
    initial_state = dict(initial_state)
    profile = initial_state.get("user_profile") or {}
    if not isinstance(profile, dict):
        return normalized
    profile = dict(profile)
    if isinstance(legacy_profile, dict):
        profile = {**legacy_profile, **profile}

    initial_state["user_profile"] = profile
    normalized["initial_state"] = initial_state
    return normalized


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
            case = _hydrate_case_images(case, yaml_dir=path.parent)
            cases.append(case)

    log.info("Loaded %d cases", len(cases))
    return cases
