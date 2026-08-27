"""benchmark 库：上传/校验/存储、内置注册、用例解析。

上传用例集用现有 ``medeval.loader.load_cases`` 校验（schema + 重复 sample_id），校验失败拒绝。
新的正式 ``cases/benchmark`` 在存在 Case 时注册为 ``source=builtin``。存储路径统一存绝对路径，便于 load_cases。
"""

from __future__ import annotations

import io
import re
import shutil
import stat
import zipfile
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any
from uuid import uuid4

import yaml
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from medeval.loader import load_cases
from medeval.models import TestCase

from . import feishu_base, feishu_sheet
from .error_messages import format_validation_exception
from .models_db import Benchmark
from .settings import Settings, get_settings


class BenchmarkValidationError(Exception):
    """上传的 benchmark 用例集校验失败（schema / 解码 / 空集 / 重复 id）。"""


class _LiteralString(str):
    """YAML 输出时强制用块文本，提升线上长回复可读性。"""


class _RepeatedCells(list):
    """同名表头下的多个单元格，和单元格内部 rich_text list 区分开。"""


_FEISHU_ROUND_LABELS = ("第一", "第二", "第三", "第四", "第五")
_IMAGE_PLACEHOLDER_RE = re.compile(
    r"\[图片[：:]\s*image_token=[A-Za-z0-9_-]+(?:[，,]\s*尺寸=\d+x\d+)?\]"
)
_ZIP_MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
_ZIP_MAX_FILES = 200
_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
_EVALUATION_MODES = {"single_turn", "multi_turn"}


def _literal_representer(dumper: yaml.SafeDumper, data: _LiteralString):
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


yaml.SafeDumper.add_representer(_LiteralString, _literal_representer)


def _literal_multiline(value: str) -> str:
    return _LiteralString(value) if "\n" in value else value


def _literalize_turn_content(case: dict[str, Any]) -> dict[str, Any]:
    item = dict(case)
    turns = item.get("turns")
    if isinstance(turns, list):
        literal_turns: list[Any] = []
        for turn in turns:
            if not isinstance(turn, dict):
                literal_turns.append(turn)
                continue
            literal_turn = dict(turn)
            content = literal_turn.get("content")
            if isinstance(content, str):
                literal_turn["content"] = _literal_multiline(content)
            literal_turns.append(literal_turn)
        item["turns"] = literal_turns
    notes = item.get("notes")
    if isinstance(notes, str):
        item["notes"] = _literal_multiline(notes)
    return item


def _safe_yaml_name(filename: str) -> str:
    name = Path(filename or "").name or "cases.yaml"
    if not name.endswith((".yaml", ".yml")):
        name = name + ".yaml"
    name = re.sub(r"[^A-Za-z0-9_.\-]", "_", name)
    return name


def _safe_sample_suffix(raw: Any, fallback: int) -> str:
    text = str(raw or "").strip() or str(fallback)
    text = re.sub(r"[^A-Za-z0-9_\-]+", "_", text)
    return text.strip("_") or str(fallback)


def _unique_online_sample_id(seen: set[str], raw: Any, fallback: int) -> str:
    base = f"online_{_safe_sample_suffix(raw, fallback)}"
    sample_id = base
    counter = 2
    while sample_id in seen:
        sample_id = f"{base}_{counter}"
        counter += 1
    seen.add(sample_id)
    return sample_id


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value).strip()
    if isinstance(value, dict):
        if "value" in value:
            return _cell_text(value.get("value"))
        if "rich_text" in value:
            parts = [_cell_text(item) for item in value.get("rich_text") or []]
            return "\n".join(part for part in parts if part).strip()
        if value.get("type") == "embed-image" and value.get("image_token"):
            token = str(value.get("image_token") or "").strip()
            width = value.get("image_width")
            height = value.get("image_height")
            size = f"，尺寸={width}x{height}" if width and height else ""
            return f"[图片：image_token={token}{size}]"
        if "text" in value:
            return str(value.get("text") or "").strip()
        if "link" in value:
            return str(value.get("text") or value.get("link") or "").strip()
        return ""
    if isinstance(value, list):
        parts = [_cell_text(item) for item in value]
        separator = "" if all(isinstance(item, dict) for item in value) else "\n"
        return separator.join(part for part in parts if part).strip()
    return str(value).strip()


def _normalise_rich_node(value: dict[str, Any]) -> dict[str, Any] | None:
    if value.get("type") == "embed-image" and value.get("image_token"):
        return dict(value)
    if "text" in value:
        node = dict(value)
        node.setdefault("type", "text")
        node["text"] = str(node.get("text") or "")
        return node if node["text"] else None
    if "link" in value:
        node = dict(value)
        node.setdefault("type", "link")
        node["text"] = str(node.get("text") or node.get("link") or "")
        return node if node["text"] or node.get("link") else None
    text = _cell_text(value)
    return {"type": "text", "text": text} if text else None


def _cell_rich_text(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [{"type": "text", "text": text}] if text else []
    if isinstance(value, (int, float, bool)):
        text = str(value).strip()
        return [{"type": "text", "text": text}] if text else []
    if isinstance(value, dict):
        if "value" in value:
            return _cell_rich_text(value.get("value"))
        if "rich_text" in value:
            nodes: list[dict[str, Any]] = []
            for item in value.get("rich_text") or []:
                if isinstance(item, dict):
                    node = _normalise_rich_node(item)
                    if node:
                        nodes.append(node)
                else:
                    nodes.extend(_cell_rich_text(item))
            return nodes
        node = _normalise_rich_node(value)
        return [node] if node else []
    if isinstance(value, list):
        nodes: list[dict[str, Any]] = []
        for item in value:
            nodes.extend(_cell_rich_text(item))
        return nodes
    text = str(value).strip()
    return [{"type": "text", "text": text}] if text else []


def _append_rich_segment(target: list[dict[str, Any]], segment: list[dict[str, Any]]) -> None:
    if not segment:
        return
    if target:
        target.append({"type": "text", "text": "\n"})
    target.extend(segment)


def _cell_image_text(value: Any) -> str:
    """只提取单元格里的真实图片占位；图片列误填普通文字时返回空。"""
    if value is None:
        return ""
    if isinstance(value, str):
        return "\n".join(_IMAGE_PLACEHOLDER_RE.findall(value)).strip()
    if isinstance(value, dict):
        if value.get("type") == "embed-image" and value.get("image_token"):
            return _cell_text(value)
        if "value" in value:
            return _cell_image_text(value.get("value"))
        if "rich_text" in value:
            return _cell_image_text(value.get("rich_text") or [])
        return ""
    if isinstance(value, list):
        parts = [_cell_image_text(item) for item in value]
        return "\n".join(part for part in parts if part).strip()
    return ""


def _normalise_feishu_header(value: str) -> str:
    return re.sub(r"[\s()（）]+", "", (value or "").strip().lower())


def _as_cell_list(value: Any) -> list[Any]:
    if isinstance(value, _RepeatedCells):
        return value
    if value is None:
        return []
    return [value]


def _field_values_by_alias(fields: dict[str, Any], aliases: list[str]) -> list[Any]:
    values: list[Any] = []
    alias_keys = {_normalise_feishu_header(alias) for alias in aliases}
    for key, value in fields.items():
        if key in aliases or _normalise_feishu_header(key) in alias_keys:
            values.extend(_as_cell_list(value))
    return values


def _field_by_alias(fields: dict[str, Any], aliases: list[str]) -> Any:
    for value in _field_values_by_alias(fields, aliases):
        if _cell_text(value) or _cell_image_text(value):
            return value
    return None


def _round_user_aliases(round_number: int, round_label: str) -> list[str]:
    prefixes = (round_label, f"第{round_number}")
    suffixes = ("用户输入", "用户文字", "用户输入文字", "用户输入内容")
    return [f"{prefix}轮{suffix}" for prefix in prefixes for suffix in suffixes]


def _round_user_image_aliases(round_number: int, round_label: str) -> list[str]:
    prefixes = (round_label, f"第{round_number}")
    return [
        f"{prefix}轮用户输入图片"
        for prefix in prefixes
    ] + [
        f"{prefix}轮用户输入(图片)"
        for prefix in prefixes
    ] + [
        f"{prefix}轮用户输入（图片）"
        for prefix in prefixes
    ]


def _round_assistant_aliases(round_number: int, round_label: str) -> list[str]:
    prefixes = (round_label, f"第{round_number}")
    suffixes = ("Cx输出", "Cx回复", "CX输出", "CX回复")
    return [f"{prefix}轮{suffix}" for prefix in prefixes for suffix in suffixes]


def _round_user_content(fields: dict[str, Any], round_number: int, round_label: str) -> str:
    text_parts = [
        _cell_text(value)
        for value in _field_values_by_alias(fields, _round_user_aliases(round_number, round_label))
    ]
    image_parts = [
        _cell_image_text(value)
        for value in _field_values_by_alias(fields, _round_user_image_aliases(round_number, round_label))
    ]
    return "\n".join(part for part in [*text_parts, *image_parts] if part).strip()


def _round_user_rich_text(
    fields: dict[str, Any], round_number: int, round_label: str
) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for value in _field_values_by_alias(fields, _round_user_aliases(round_number, round_label)):
        _append_rich_segment(nodes, _cell_rich_text(value))
    for value in _field_values_by_alias(fields, _round_user_image_aliases(round_number, round_label)):
        _append_rich_segment(nodes, _cell_rich_text(value))
    return nodes


def _round_assistant_content(fields: dict[str, Any], round_number: int, round_label: str) -> str:
    parts = [
        _cell_text(value)
        for value in _field_values_by_alias(fields, _round_assistant_aliases(round_number, round_label))
    ]
    return "\n".join(part for part in parts if part).strip()


def _round_assistant_rich_text(
    fields: dict[str, Any], round_number: int, round_label: str
) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for value in _field_values_by_alias(fields, _round_assistant_aliases(round_number, round_label)):
        _append_rich_segment(nodes, _cell_rich_text(value))
    return nodes


def _feishu_row_turns(fields: dict[str, Any]) -> list[dict[str, str]]:
    turns: list[dict[str, str]] = []
    for round_number, round_label in enumerate(_FEISHU_ROUND_LABELS, start=1):
        user = _round_user_content(fields, round_number, round_label)
        assistant = _round_assistant_content(fields, round_number, round_label)
        if user:
            turns.append({"role": "user", "content": _literal_multiline(user)})
        if assistant:
            turns.append({"role": "assistant", "content": _literal_multiline(assistant)})
    return turns


def _feishu_row_rich_messages(fields: dict[str, Any]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for round_number, round_label in enumerate(_FEISHU_ROUND_LABELS, start=1):
        user = _round_user_content(fields, round_number, round_label)
        user_rich = _round_user_rich_text(fields, round_number, round_label)
        assistant = _round_assistant_content(fields, round_number, round_label)
        assistant_rich = _round_assistant_rich_text(fields, round_number, round_label)
        if user:
            messages.append({"role": "user", "content": user, "rich_text": user_rich})
        if assistant:
            messages.append(
                {"role": "assistant", "content": assistant, "rich_text": assistant_rich}
            )
    return messages


def _sheet_row_fields(headers: list[str], row: list[Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for col_index, cell in enumerate(row):
        if col_index >= len(headers) or not headers[col_index]:
            continue
        fields.setdefault(headers[col_index], _RepeatedCells()).append(cell)
    return fields


def _user_profile_text(fields: dict[str, Any]) -> str:
    return _cell_text(_field_by_alias(fields, ["用户档案", "用户画像", "用户信息"]))


def _case_notes(*, user_profile: str = "", attachment_notes: str = "") -> str:
    parts: list[str] = []
    if user_profile.strip():
        parts.append(f"用户档案：\n{user_profile.strip()}")
    if attachment_notes.strip():
        parts.append(attachment_notes.strip())
    return _literal_multiline("\n\n".join(parts)) if parts else ""


def _attachment_notes(value: Any) -> str:
    if not isinstance(value, list):
        return ""
    notes: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("file_token") or "").strip()
        url = str(item.get("url") or item.get("tmp_url") or "").strip()
        if name and url:
            notes.append(f"{name} ({url})")
        elif name:
            notes.append(name)
    return "；".join(notes)


def _collect_levels(cases: list[TestCase]) -> list[str]:
    return sorted({getattr(c.level, "value", c.level) for c in cases})


def _normalise_default_evaluation_mode(value: str | None) -> str:
    mode = str(value or "single_turn").strip()
    if mode not in _EVALUATION_MODES:
        raise BenchmarkValidationError("默认对话模式必须是单轮或多轮")
    return mode


def _validate_yaml_path(path: Path, settings: Settings) -> list[TestCase]:
    try:
        cases = load_cases(include=[str(path)], base_dir=settings.project_root)
    except ValidationError as exc:
        raise BenchmarkValidationError(
            format_validation_exception(exc, prefix="用例校验失败")
        ) from exc
    except Exception as exc:  # noqa: BLE001 —— loader 校验失败统一转领域错误
        message = str(exc).split(": ", 1)[-1].strip()
        raise BenchmarkValidationError(
            f"用例校验失败：{message}"
            if message
            else "用例校验失败，请检查用例内容和字段格式"
        ) from exc
    if not cases:
        raise BenchmarkValidationError("用例集为空或不含合法用例")
    return cases


def _validate_yaml_bytes(content: bytes, settings: Settings) -> tuple[Path, list[TestCase]]:
    """把上传内容写到暂存文件并用 loader 校验。返回 (暂存路径, 用例列表)。"""
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BenchmarkValidationError("文件编码不正确，请将文件保存为 UTF-8 编码后重试") from exc

    staging = settings.uploads_dir / "_staging"
    staging.mkdir(parents=True, exist_ok=True)
    tmp = staging / f"{uuid4().hex}.yaml"
    tmp.write_text(text, encoding="utf-8")
    try:
        cases = _validate_yaml_path(tmp, settings)
    except BenchmarkValidationError:
        tmp.unlink(missing_ok=True)
        raise
    return tmp, cases


def _validate_and_extract_zip(content: bytes, settings: Settings) -> tuple[Path, list[TestCase]]:
    """安全解压标准 benchmark 包，并校验 cases.yaml 对图片的引用。

    接受 ZIP 根目录，或 macOS「压缩文件夹」时自动生成的单层目录包装。
    解压后的 benchmark 存储始终规范为 ``cases.yaml`` + ``images/``。
    """
    staging = settings.uploads_dir / "_staging" / uuid4().hex
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise BenchmarkValidationError("上传文件不是有效 ZIP 包") from exc

    try:
        infos = archive.infolist()
        if len(infos) > _ZIP_MAX_FILES:
            raise BenchmarkValidationError(f"ZIP 文件数超过上限（{_ZIP_MAX_FILES}）")
        members: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []
        for info in infos:
            raw_name = info.filename.replace("\\", "/")
            if not raw_name:
                continue
            path = PurePosixPath(raw_name)
            if "__MACOSX" in path.parts or path.name == ".DS_Store":
                continue
            if path.is_absolute() or ".." in path.parts or raw_name.startswith("/"):
                raise BenchmarkValidationError(f"ZIP 含不安全路径：{info.filename}")
            mode = info.external_attr >> 16
            if stat.S_IFMT(mode) == stat.S_IFLNK:
                raise BenchmarkValidationError(f"ZIP 不允许符号链接：{info.filename}")
            if info.is_dir():
                continue
            members.append((info, path))

        has_root_cases = any(path.parts == ("cases.yaml",) for _, path in members)
        top_level_parts = {path.parts[0] for _, path in members if len(path.parts) >= 2}
        wrapper = ()
        if not has_root_cases:
            if len(top_level_parts) == 1:
                candidate = next(iter(top_level_parts))
                if any(path.parts == (candidate, "cases.yaml") for _, path in members):
                    wrapper = (candidate,)
            if not wrapper:
                raise BenchmarkValidationError("ZIP 根目录必须包含 cases.yaml，或只包含一层目录包装")

        total_size = 0
        case_found = False
        normalized_members: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []
        for info, path in members:
            if wrapper:
                if len(path.parts) <= 1 or path.parts[0] != wrapper[0]:
                    raise BenchmarkValidationError("ZIP 仅允许包含一个顶层目录，其中应有 cases.yaml 和 images/")
                path = PurePosixPath(*path.parts[1:])
            total_size += info.file_size
            if total_size > _ZIP_MAX_UNCOMPRESSED_BYTES:
                raise BenchmarkValidationError("ZIP 解压后内容超过 100 MiB 限制")
            if path.parts == ("cases.yaml",):
                case_found = True
                normalized_members.append((info, path))
                continue
            if not path.parts or path.parts[0] != "images" or len(path.parts) < 2:
                raise BenchmarkValidationError("ZIP 仅允许包含 cases.yaml 和 images/ 目录")
            if path.suffix.lower() not in _IMAGE_SUFFIXES:
                raise BenchmarkValidationError(f"images/ 中存在不支持的图片格式：{info.filename}")
            if info.file_size > 10 * 1024 * 1024:
                raise BenchmarkValidationError(f"单张图片超过 10 MiB 限制：{info.filename}")
            normalized_members.append((info, path))
        if not case_found:
            raise BenchmarkValidationError("ZIP 中未找到 cases.yaml")

        staging.mkdir(parents=True, exist_ok=False)
        for info, path in normalized_members:
            target = staging.joinpath(*path.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as dest:
                shutil.copyfileobj(source, dest)
        cases = _validate_yaml_path(staging / "cases.yaml", settings)
        return staging, cases
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    finally:
        archive.close()


def _create_uploaded_benchmark_from_yaml_bytes(
    session: Session,
    *,
    name: str,
    yaml_content: bytes,
    filename: str,
    description: str = "",
    version: str = "v1",
    created_by: str | None = None,
    source: str = "offline",
    default_evaluation_mode: str = "single_turn",
    settings: Settings | None = None,
) -> Benchmark:
    settings = settings or get_settings()
    name = (name or "").strip() or "未命名 benchmark"
    existing = session.execute(
        select(Benchmark).where(Benchmark.name == name)
    ).scalars().first()
    if existing is not None:
        raise BenchmarkValidationError(f"benchmark 名称「{name}」已存在，请换一个名称")
    tmp, cases = _validate_yaml_bytes(yaml_content, settings)

    default_evaluation_mode = _normalise_default_evaluation_mode(default_evaluation_mode)
    row = Benchmark(
        name=name,
        description=description,
        version=version or "v1",
        source=source,
        case_count=len(cases),
        tags=[],
        levels=_collect_levels(cases),
        storage_path="",
        created_by=created_by,
    )
    row.default_evaluation_mode = default_evaluation_mode
    session.add(row)
    session.flush()

    dest_dir = settings.uploads_dir / str(row.id)
    # 数据库从空库重建时，ID 可能与磁盘上的孤儿目录重复；新建记录只保留本次上传。
    shutil.rmtree(dest_dir, ignore_errors=True)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / _safe_yaml_name(filename)
    tmp.replace(dest)
    row.storage_path = str(dest_dir)
    return row


def _create_uploaded_benchmark_from_zip_bytes(
    session: Session,
    *,
    name: str,
    zip_content: bytes,
    description: str = "",
    version: str = "v1",
    created_by: str | None = None,
    source: str = "offline",
    default_evaluation_mode: str = "single_turn",
    settings: Settings | None = None,
) -> Benchmark:
    """创建包含 ``cases.yaml`` 与 ``images/`` 的 ZIP benchmark。"""
    settings = settings or get_settings()
    name = (name or "").strip() or "未命名 benchmark"
    existing = session.execute(
        select(Benchmark).where(Benchmark.name == name)
    ).scalars().first()
    if existing is not None:
        raise BenchmarkValidationError(f"benchmark 名称「{name}」已存在，请换一个名称")
    staged_dir, cases = _validate_and_extract_zip(zip_content, settings)

    default_evaluation_mode = _normalise_default_evaluation_mode(default_evaluation_mode)
    row = Benchmark(
        name=name,
        description=description,
        version=version or "v1",
        source=source,
        case_count=len(cases),
        tags=[],
        levels=_collect_levels(cases),
        storage_path="",
        created_by=created_by,
    )
    row.default_evaluation_mode = default_evaluation_mode
    session.add(row)
    session.flush()
    dest_dir = settings.uploads_dir / str(row.id)
    shutil.rmtree(dest_dir, ignore_errors=True)
    staged_dir.replace(dest_dir)
    row.storage_path = str(dest_dir)
    return row


def feishu_base_records_to_yaml_bytes(records: list[dict[str, Any]]) -> bytes:
    """把飞书 Base 记录转为线上 benchmark YAML，完整保留每轮对话。"""
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, record in enumerate(records, start=1):
        fields = record.get("fields") if isinstance(record, dict) else {}
        if not isinstance(fields, dict):
            continue
        turns = _feishu_row_turns(fields)
        if not turns:
            continue
        rich_messages = _feishu_row_rich_messages(fields)

        sample_id = _unique_online_sample_id(seen, record.get("record_id"), index)

        case: dict[str, Any] = {
            "schema_version": "2.0",
            "sample_id": sample_id,
            "scenario": "线上真实对话",
            "level": "L2",
            "source": "online",
            "turns": turns,
            "evaluation": {
                "dimension_criteria": {},
                "guidelines": [],
                "model_comparison_dimension_criteria": {},
                "model_comparison_guidelines": [],
            },
        }
        image_notes = _attachment_notes(fields.get("第一轮用户输入(图片)"))
        notes = _case_notes(
            user_profile=_user_profile_text(fields),
            attachment_notes=f"第一轮用户输入(图片)：{image_notes}" if image_notes else "",
        )
        if notes:
            case["notes"] = notes
        if rich_messages:
            case["rich_messages"] = rich_messages
        cases.append(case)

    if not cases:
        raise BenchmarkValidationError("飞书 Base 中没有可转换的线上对话")
    return yaml.safe_dump(cases, allow_unicode=True, sort_keys=False).encode("utf-8")


def _sheet_to_cases(sheet: dict[str, Any], seen: set[str]) -> list[dict[str, Any]]:
    """把单个飞书工作表单元格转为线上对话用例；共用 seen 保证 sample_id 全局唯一。"""
    cells = sheet.get("cells") or []
    row_indices = sheet.get("row_indices") or []
    if not cells or not isinstance(cells, list):
        return []

    headers = [_cell_text(cell) for cell in cells[0]]
    cases: list[dict[str, Any]] = []
    for index, row in enumerate(cells[1:], start=1):
        if not isinstance(row, list):
            continue
        fields = _sheet_row_fields(headers, row)
        turns = _feishu_row_turns(fields)
        if not turns:
            continue
        rich_messages = _feishu_row_rich_messages(fields)

        row_number = row_indices[index] if index < len(row_indices) else index + 1
        raw_id = f"{sheet.get('sheet_name') or sheet.get('sheet_id') or 'sheet'}_{row_number}"
        sample_id = _unique_online_sample_id(seen, raw_id, index)
        case: dict[str, Any] = {
            "schema_version": "2.0",
            "sample_id": sample_id,
            "scenario": "线上真实对话",
            "level": "L2",
            "source": "online",
            "turns": turns,
            "evaluation": {
                "dimension_criteria": {},
                "guidelines": [],
                "model_comparison_dimension_criteria": {},
                "model_comparison_guidelines": [],
            },
        }
        notes = _case_notes(user_profile=_user_profile_text(fields))
        if notes:
            case["notes"] = notes
        if rich_messages:
            case["rich_messages"] = rich_messages
        cases.append(case)
    return cases


def feishu_sheet_cells_to_yaml_bytes(sheets: list[dict[str, Any]]) -> bytes:
    """把飞书 Sheet 多个工作表单元格汇总为线上 benchmark YAML，保留多轮文本与图片 token。"""
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    for sheet in sheets:
        cases.extend(_sheet_to_cases(sheet, seen))

    if not cases:
        raise BenchmarkValidationError("飞书 Sheet 中没有可转换的线上对话")
    return yaml.safe_dump(cases, allow_unicode=True, sort_keys=False).encode("utf-8")


def feishu_url_to_yaml_bytes(access_token: str, source_url: str) -> bytes:
    if feishu_base.is_base_url(source_url):
        try:
            records = feishu_base.fetch_base_records(access_token, source_url)
        except feishu_base.FeishuBaseError as exc:
            raise BenchmarkValidationError(str(exc)) from exc
        return feishu_base_records_to_yaml_bytes(records)
    if feishu_sheet.is_sheet_url(source_url):
        try:
            sheets = feishu_sheet.fetch_sheet_cells(access_token, source_url)
        except feishu_sheet.FeishuSheetError as exc:
            raise BenchmarkValidationError(str(exc)) from exc
        return feishu_sheet_cells_to_yaml_bytes(sheets)
    raise BenchmarkValidationError("飞书 URL 需为 Base、Sheet 或 Wiki Sheet 链接")


def create_uploaded_benchmark_from_feishu_url(
    session: Session,
    *,
    name: str,
    source_url: str,
    access_token: str,
    description: str = "",
    version: str = "v1",
    created_by: str | None = None,
    default_evaluation_mode: str = "single_turn",
    settings: Settings | None = None,
) -> Benchmark:
    yaml_content = feishu_url_to_yaml_bytes(access_token, source_url)
    return _create_uploaded_benchmark_from_yaml_bytes(
        session,
        name=name,
        yaml_content=yaml_content,
        filename=f"{name}.yaml",
        description=description,
        version=version,
        created_by=created_by,
        source="online",
        default_evaluation_mode=default_evaluation_mode,
        settings=settings,
    )


def create_uploaded_benchmark_from_feishu_base(
    session: Session,
    *,
    name: str,
    source_url: str,
    access_token: str,
    description: str = "",
    version: str = "v1",
    created_by: str | None = None,
    default_evaluation_mode: str = "single_turn",
    settings: Settings | None = None,
) -> Benchmark:
    return create_uploaded_benchmark_from_feishu_url(
        session,
        name=name,
        source_url=source_url,
        access_token=access_token,
        description=description,
        version=version,
        created_by=created_by,
        default_evaluation_mode=default_evaluation_mode,
        settings=settings,
    )


def _replace_uploaded_benchmark_with_yaml_bytes(
    session: Session,
    benchmark: Benchmark,
    *,
    yaml_content: bytes,
    filename: str,
    source: str,
    default_evaluation_mode: str | None = None,
    settings: Settings | None = None,
) -> Benchmark:
    settings = settings or get_settings()
    if benchmark.source == "builtin":
        raise BenchmarkValidationError("内置 benchmark 不可覆盖")
    tmp, cases = _validate_yaml_bytes(yaml_content, settings)

    dest_dir = settings.uploads_dir / str(benchmark.id)
    shutil.rmtree(dest_dir, ignore_errors=True)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / _safe_yaml_name(filename)
    tmp.replace(dest)

    benchmark.case_count = len(cases)
    if default_evaluation_mode is not None:
        benchmark.default_evaluation_mode = _normalise_default_evaluation_mode(default_evaluation_mode)
    benchmark.levels = _collect_levels(cases)
    benchmark.storage_path = str(dest_dir)
    benchmark.source = source
    benchmark.mark_updated()
    _invalidate_cases_cache(benchmark.storage_path)
    return benchmark


def _replace_uploaded_benchmark_with_zip_bytes(
    session: Session,
    benchmark: Benchmark,
    *,
    zip_content: bytes,
    source: str,
    default_evaluation_mode: str | None = None,
    settings: Settings | None = None,
) -> Benchmark:
    settings = settings or get_settings()
    if benchmark.source == "builtin":
        raise BenchmarkValidationError("内置 benchmark 不可覆盖")
    staged_dir, cases = _validate_and_extract_zip(zip_content, settings)
    dest_dir = settings.uploads_dir / str(benchmark.id)
    shutil.rmtree(dest_dir, ignore_errors=True)
    staged_dir.replace(dest_dir)

    benchmark.case_count = len(cases)
    if default_evaluation_mode is not None:
        benchmark.default_evaluation_mode = _normalise_default_evaluation_mode(default_evaluation_mode)
    benchmark.levels = _collect_levels(cases)
    benchmark.storage_path = str(dest_dir)
    benchmark.source = source
    benchmark.mark_updated()
    _invalidate_cases_cache(benchmark.storage_path)
    return benchmark


def replace_uploaded_benchmark_from_feishu_url(
    session: Session,
    benchmark: Benchmark,
    *,
    source_url: str,
    access_token: str,
    default_evaluation_mode: str | None = None,
    settings: Settings | None = None,
) -> Benchmark:
    yaml_content = feishu_url_to_yaml_bytes(access_token, source_url)
    return _replace_uploaded_benchmark_with_yaml_bytes(
        session,
        benchmark,
        yaml_content=yaml_content,
        filename=f"{benchmark.name}.yaml",
        source="online",
        default_evaluation_mode=default_evaluation_mode,
        settings=settings,
    )


def replace_uploaded_benchmark_from_feishu_base(
    session: Session,
    benchmark: Benchmark,
    *,
    source_url: str,
    access_token: str,
    settings: Settings | None = None,
) -> Benchmark:
    return replace_uploaded_benchmark_from_feishu_url(
        session,
        benchmark,
        source_url=source_url,
        access_token=access_token,
        settings=settings,
    )


def _copy_appended_images(source_root: Path, destination_root: Path) -> None:
    """把追加包的 images/ 合入暂存目录；同路径文件一律拒绝，避免静默串图。"""
    source_images = source_root / "images"
    if not source_images.is_dir():
        return
    destination_images = destination_root / "images"
    for source in sorted(path for path in source_images.rglob("*") if path.is_file()):
        relative = source.relative_to(source_images)
        destination = destination_images / relative
        if destination.exists():
            raise BenchmarkValidationError(
                f"追加包图片路径与现有文件重复：images/{relative.as_posix()}"
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _replace_storage_atomically(staged_dir: Path, destination: Path) -> None:
    backup = destination.with_name(f".{destination.name}.backup-{uuid4().hex}")
    if destination.exists():
        destination.replace(backup)
    try:
        staged_dir.replace(destination)
    except Exception:
        if backup.exists():
            backup.replace(destination)
        raise
    else:
        shutil.rmtree(backup, ignore_errors=True)


def _append_validated_cases(
    benchmark: Benchmark,
    incoming_cases: list[TestCase],
    *,
    incoming_root: Path | None,
    settings: Settings,
) -> Benchmark:
    if benchmark.source == "builtin":
        raise BenchmarkValidationError("内置 benchmark 不可追加")

    existing_cases = load_benchmark_cases(benchmark, settings=settings)
    existing_ids = {case.sample_id for case in existing_cases}
    duplicate_ids = sorted(
        existing_ids.intersection(case.sample_id for case in incoming_cases)
    )
    if duplicate_ids:
        preview = "、".join(duplicate_ids[:5])
        suffix = f" 等 {len(duplicate_ids)} 条" if len(duplicate_ids) > 5 else ""
        raise BenchmarkValidationError(f"sample_id 与现有用例重复：{preview}{suffix}")

    staged_dir = settings.uploads_dir / "_staging" / uuid4().hex
    staged_dir.mkdir(parents=True, exist_ok=False)
    try:
        existing_root = _storage_root(benchmark, settings)
        existing_images = existing_root / "images"
        if existing_images.is_dir():
            shutil.copytree(existing_images, staged_dir / "images")
        if incoming_root is not None:
            _copy_appended_images(incoming_root, staged_dir)

        combined = [*existing_cases, *incoming_cases]
        serialized = [
            _literalize_turn_content(
                case.model_dump(mode="json", by_alias=True, exclude={"case_file"})
            )
            for case in combined
        ]
        (staged_dir / "cases.yaml").write_text(
            yaml.safe_dump(serialized, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        validated = _validate_yaml_path(staged_dir / "cases.yaml", settings)

        destination = settings.uploads_dir / str(benchmark.id)
        _replace_storage_atomically(staged_dir, destination)
        benchmark.case_count = len(validated)
        benchmark.levels = _collect_levels(validated)
        benchmark.storage_path = str(destination)
        benchmark.mark_updated()
        _invalidate_cases_cache(benchmark.storage_path)
        return benchmark
    except Exception:
        shutil.rmtree(staged_dir, ignore_errors=True)
        raise


def append_uploaded_benchmark(
    session: Session,
    benchmark: Benchmark,
    *,
    content: bytes,
    filename: str = "cases.yaml",
    settings: Settings | None = None,
) -> Benchmark:
    """校验后把 YAML/ZIP 中的新 Case 原子追加到现有上传 benchmark。"""
    settings = settings or get_settings()
    staged_source: Path | None = None
    try:
        if Path(filename).suffix.lower() == ".zip":
            staged_source, incoming_cases = _validate_and_extract_zip(content, settings)
            incoming_root = staged_source
        else:
            staged_source, incoming_cases = _validate_yaml_bytes(content, settings)
            incoming_root = None
        result = _append_validated_cases(
            benchmark,
            incoming_cases,
            incoming_root=incoming_root,
            settings=settings,
        )
        session.flush()
        return result
    finally:
        if staged_source is not None:
            if staged_source.is_dir():
                shutil.rmtree(staged_source, ignore_errors=True)
            else:
                staged_source.unlink(missing_ok=True)


def append_uploaded_benchmark_from_feishu_url(
    session: Session,
    benchmark: Benchmark,
    *,
    source_url: str,
    access_token: str,
    settings: Settings | None = None,
) -> Benchmark:
    yaml_content = feishu_url_to_yaml_bytes(access_token, source_url)
    return append_uploaded_benchmark(
        session,
        benchmark,
        content=yaml_content,
        filename="cases.yaml",
        settings=settings,
    )


def create_uploaded_benchmark(
    session: Session,
    *,
    name: str,
    content: bytes,
    filename: str = "cases.yaml",
    description: str = "",
    version: str = "v1",
    created_by: str | None = None,
    source: str = "offline",
    default_evaluation_mode: str = "single_turn",
    settings: Settings | None = None,
) -> Benchmark:
    """校验并保存一个上传的 benchmark；校验失败抛 BenchmarkValidationError。"""
    settings = settings or get_settings()
    name = (name or "").strip() or "未命名 benchmark"
    source = source if source in {"online", "offline"} else "offline"
    # 线上 benchmark 只能通过飞书 Base URL 导入（见 create_uploaded_benchmark_from_feishu_url）；
    # 文件上传仅支持 offline YAML，不再解析线上 JSONL。
    if source == "online":
        raise BenchmarkValidationError("线上 benchmark 只能通过飞书 Base URL 导入，不支持文件上传")
    if Path(filename).suffix.lower() == ".zip":
        return _create_uploaded_benchmark_from_zip_bytes(
            session,
            name=name,
            zip_content=content,
            description=description,
            version=version or "v1",
            source=source,
            created_by=created_by,
            default_evaluation_mode=default_evaluation_mode,
            settings=settings,
        )
    return _create_uploaded_benchmark_from_yaml_bytes(
        session,
        name=name,
        yaml_content=content,
        filename=filename,
        description=description,
        version=version or "v1",
        source=source,
        created_by=created_by,
        default_evaluation_mode=default_evaluation_mode,
        settings=settings,
    )


# 派生 benchmark 只允许覆盖 V2 evaluation。
_CASE_OVERRIDE_FIELDS = ("evaluation",)


def _apply_case_overrides(
    cases: list[TestCase], case_overrides: list[dict[str, Any]]
) -> list[TestCase]:
    """按 sample_id 把判据覆盖套到对应用例上，逐条经 TestCase 校验。

    - 未匹配 sample_id（不在源 benchmark）：**跳过丢弃**（不新增、不报错）；
    - 一条都没匹配上：抛 BenchmarkValidationError；
    - 非法覆盖（不符合 schema）：抛 BenchmarkValidationError。

    返回新的用例列表（保持原顺序），源用例对象不被修改。
    """
    by_id = {c.sample_id: c for c in cases}
    matched = 0
    for ov in case_overrides:
        sid = (ov or {}).get("sample_id")
        if not sid:
            raise BenchmarkValidationError("case 覆盖缺少 sample_id")
        base = by_id.get(sid)
        if base is None:
            continue  # 未匹配 sample_id 直接丢弃
        data = base.model_dump(mode="json")
        for field in _CASE_OVERRIDE_FIELDS:
            if ov.get(field) is not None:
                data[field] = ov[field]
        try:
            by_id[sid] = TestCase.model_validate(data)
        except ValidationError as exc:
            raise BenchmarkValidationError(
                format_validation_exception(exc, prefix=f"用例 {sid} 判据校验失败")
            ) from exc
        matched += 1
    if case_overrides and matched == 0:
        raise BenchmarkValidationError(
            "没有任何用例 sample_id 匹配源 benchmark，未做任何改动"
        )
    return [by_id[c.sample_id] for c in cases]


def derive_benchmark_with_overrides(
    session: Session,
    source: Benchmark,
    *,
    name: str,
    case_overrides: list[dict[str, Any]],
    description: str = "",
    created_by: str | None = None,
    settings: Settings | None = None,
) -> Benchmark:
    """复制源 benchmark 全部用例、按 sample_id 套用判据覆盖，另存为新的 uploaded benchmark。

    源 benchmark（含内置用例集）只读不改。新 benchmark 记录 created_by。
    """
    settings = settings or get_settings()
    cases = load_benchmark_cases(source, settings=settings)
    if not cases:
        raise BenchmarkValidationError("源 benchmark 无可加载用例")
    edited = _apply_case_overrides(cases, case_overrides or [])
    # 序列化为单个 YAML，复用 create_uploaded_benchmark 的校验 + 唯一名 + 落盘。
    # 剔除 loader 注入、不应入用例正文的 case_file 字段。
    payload = []
    for c in edited:
        d = c.model_dump(mode="json")
        d.pop("case_file", None)
        payload.append(d)
    text = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
    derived = create_uploaded_benchmark(
        session,
        name=name,
        content=text.encode("utf-8"),
        filename=f"{name}.yaml",
        description=description,
        created_by=created_by,
        settings=settings,
    )
    derived.default_evaluation_mode = source.default_evaluation_mode
    derived.suite_type = source.suite_type
    return derived


def _yaml_to_case_overrides(yaml_text: str) -> list[dict[str, Any]]:
    """把整段用例 YAML 解析成判据覆盖列表（按 sample_id 取判据字段，其余忽略）。

    顶层须为用例 dict 列表；无任何带 sample_id 的用例时抛 BenchmarkValidationError。
    """
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        raise BenchmarkValidationError("YAML 解析失败，请检查缩进、冒号和列表格式") from exc
    if not isinstance(data, list):
        raise BenchmarkValidationError("YAML 顶层须为用例列表")

    overrides: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict) or not item.get("sample_id"):
            continue
        ov: dict[str, Any] = {"sample_id": item["sample_id"]}
        for field in _CASE_OVERRIDE_FIELDS:
            if item.get(field) is not None:
                ov[field] = item[field]
        overrides.append(ov)
    if not overrides:
        raise BenchmarkValidationError("YAML 中无任何带 sample_id 的用例")
    return overrides


def derive_benchmark_from_yaml(
    session: Session,
    source: Benchmark,
    *,
    name: str,
    yaml_text: str,
    description: str = "",
    created_by: str | None = None,
    settings: Settings | None = None,
) -> Benchmark:
    """从整段用例 YAML 解析判据覆盖，派生新 benchmark（只合并判据字段，未匹配 sample_id 丢弃）。

    YAML 须为用例 dict 列表；每条按 sample_id 取判据字段（其余字段如 turns 忽略）。
    """
    overrides = _yaml_to_case_overrides(yaml_text)
    return derive_benchmark_with_overrides(
        session,
        source,
        name=name,
        case_overrides=overrides,
        description=description,
        created_by=created_by,
        settings=settings,
    )


def overwrite_benchmark_from_yaml(
    session: Session,
    target: Benchmark,
    *,
    yaml_text: str,
    settings: Settings | None = None,
) -> Benchmark:
    """从整段用例 YAML 改判据，**就地覆盖**原 benchmark（合并语义与另存完全一致）。

    复制源集全部用例、按 sample_id 只合并判据字段、未匹配 sample_id 丢弃、零匹配报错，
    源集中不在本次编辑的用例原样保留；最终写回 ``target`` 自身（非新建）。内置不可覆盖。
    """
    settings = settings or get_settings()
    if target.source == "builtin":
        raise BenchmarkValidationError("内置 benchmark 不可覆盖")
    overrides = _yaml_to_case_overrides(yaml_text)
    cases = load_benchmark_cases(target, settings=settings)
    if not cases:
        raise BenchmarkValidationError("benchmark 无可加载用例")
    edited = _apply_case_overrides(cases, overrides)
    payload = []
    for c in edited:
        d = c.model_dump(mode="json")
        d.pop("case_file", None)
        payload.append(d)
    text = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
    return replace_uploaded_benchmark(
        session,
        target,
        content=text.encode("utf-8"),
        filename=f"{target.name}.yaml",
        settings=settings,
    )


def ensure_builtin_benchmark(
    session: Session, settings: Settings | None = None
) -> Benchmark | None:
    """若新版正式 benchmark 已有 Case 则注册；空目录不创建记录。"""
    settings = settings or get_settings()
    existing = session.execute(
        select(Benchmark).where(Benchmark.source == "builtin")
    ).scalars().first()
    cases_dir = settings.project_root / settings.builtin_cases_dir
    if not cases_dir.is_dir():
        return existing
    cases = load_cases(include=[str(cases_dir)], base_dir=settings.project_root)
    if existing is not None:
        # ponytail: 列表展示 case_count 须与磁盘同步，否则用例增删后仍显示旧值（如 71 vs 92）
        existing.case_count = len(cases)
        existing.tags = []
        existing.levels = _collect_levels(cases)
        session.flush()
        return existing

    if not cases:
        return None
    row = Benchmark(
        name="乳腺癌专科 benchmark",
        description="固定八维与指南评分正式套件（cases/benchmark）",
        version="v2",
        source="builtin",
        case_count=len(cases),
        tags=[],
        levels=_collect_levels(cases),
        storage_path=str(cases_dir),
    )
    session.add(row)
    session.flush()
    return row


def replace_uploaded_benchmark(
    session: Session,
    benchmark: Benchmark,
    *,
    content: bytes,
    filename: str = "cases.yaml",
    source: str | None = None,
    default_evaluation_mode: str | None = None,
    settings: Settings | None = None,
) -> Benchmark:
    """用新内容覆盖一个已上传的 benchmark（保留 id/name）。builtin 不可覆盖。"""
    settings = settings or get_settings()
    if benchmark.source == "builtin":
        raise BenchmarkValidationError("内置 benchmark 不可覆盖")
    next_source = source if source in {"online", "offline"} else benchmark.source
    next_source = next_source if next_source in {"online", "offline"} else "offline"
    # 线上 benchmark 只能通过飞书 Base URL 覆盖（见 replace_uploaded_benchmark_from_feishu_url）。
    if next_source == "online":
        raise BenchmarkValidationError("线上 benchmark 只能通过飞书 Base URL 覆盖，不支持文件上传")
    if Path(filename).suffix.lower() == ".zip":
        return _replace_uploaded_benchmark_with_zip_bytes(
            session,
            benchmark,
            zip_content=content,
            source=next_source,
            default_evaluation_mode=default_evaluation_mode,
            settings=settings,
        )
    return _replace_uploaded_benchmark_with_yaml_bytes(
        session,
        benchmark,
        yaml_content=content,
        filename=filename,
        source=next_source,
        default_evaluation_mode=default_evaluation_mode,
        settings=settings,
    )


def export_benchmark_yaml(
    benchmark: Benchmark, settings: Settings | None = None
) -> tuple[str, str]:
    """导出 benchmark 为单个 YAML 文本，返回 (ascii 文件名, 文本)。

    uploaded 返回原始上传文件内容（保真）；builtin 把全部用例合并导出。
    """
    settings = settings or get_settings()
    storage = Path(benchmark.storage_path)
    if benchmark.source != "builtin" and storage.is_dir():
        files = sorted(storage.glob("*.yaml")) + sorted(storage.glob("*.yml"))
        if files:
            return files[0].name, files[0].read_text(encoding="utf-8")

    cases = load_benchmark_cases(benchmark, settings=settings)
    data = [c.model_dump(mode="json") for c in cases]
    text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    return f"benchmark_{benchmark.id}.yaml", text


def resolve_cases_path(benchmark: Benchmark) -> Path:
    """benchmark 用例所在路径（绝对）。"""
    return Path(benchmark.storage_path)


# 用例解析结果缓存：键 = (storage_path, mtime)。
# 返回深拷贝，保证调用方拿到与「每次重新解析」一致的独立对象，不会被其他请求改动污染。
_CASES_CACHE: dict[tuple, list[TestCase]] = {}


def _path_mtime(path: str, settings: Settings) -> float | None:
    p = Path(path)
    if not p.is_absolute():
        p = settings.project_root / p
    try:
        return p.stat().st_mtime
    except OSError:
        return None


def load_benchmark_cases(
    benchmark: Benchmark,
    *,
    settings: Settings | None = None,
) -> list[TestCase]:
    """加载某 benchmark 的 V2 用例。

    按 ``(storage_path, mtime)`` 做进程内缓存；
    文件被覆盖（mtime 变化）即自动失效。返回深拷贝以隔离调用方的就地修改。
    """
    settings = settings or get_settings()
    mtime = _path_mtime(benchmark.storage_path, settings)
    key = (benchmark.storage_path, mtime)
    if mtime is not None:
        cached = _CASES_CACHE.get(key)
        if cached is not None:
            return [c.model_copy(deep=True) for c in cached]
    cases = load_cases(
        include=[benchmark.storage_path],
        base_dir=settings.project_root,
    )
    if mtime is not None:
        _CASES_CACHE[key] = cases
        return [c.model_copy(deep=True) for c in cases]
    return cases


def _storage_root(benchmark: Benchmark, settings: Settings) -> Path:
    root = Path(benchmark.storage_path)
    if not root.is_absolute():
        root = settings.project_root / root
    return root


def _invalidate_cases_cache(storage_path: str) -> None:
    for key in list(_CASES_CACHE):
        if key[0] == storage_path:
            del _CASES_CACHE[key]


def _parse_single_case_yaml(yaml_text: str, *, expected_sample_id: str) -> dict[str, Any]:
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        raise BenchmarkValidationError("YAML 解析失败，请检查缩进、冒号和列表格式") from exc
    if isinstance(data, dict) and "cases" not in data:
        item = data
    elif isinstance(data, list) and len(data) == 1:
        item = data[0]
    else:
        raise BenchmarkValidationError("YAML 须为单条用例对象或仅含一条用例的列表")
    if not isinstance(item, dict):
        raise BenchmarkValidationError("用例须为 mapping")
    sid = str(item.get("sample_id") or "").strip()
    if sid != expected_sample_id:
        raise BenchmarkValidationError(f"sample_id 须为 {expected_sample_id}，实际为 {sid or '(空)'}")
    return item


def _source_case_entries(raw: Any) -> tuple[list[Any], str]:
    """返回源 YAML 的用例条目及顶层布局，兼容 loader 支持的三种格式。"""
    if isinstance(raw, list):
        return raw, "list"
    if isinstance(raw, dict) and "cases" in raw:
        entries = raw.get("cases")
        if not isinstance(entries, list):
            raise BenchmarkValidationError("源 YAML 的 cases 须为用例列表")
        return entries, "suite"
    if isinstance(raw, dict):
        return [raw], "single"
    raise BenchmarkValidationError("源 YAML 顶层须为单条用例、用例列表或含 cases 的用例集")


def _rebuild_source_root(raw: Any, entries: list[Any], layout: str) -> Any:
    """按源 YAML 原有布局重建顶层，避免编辑一条 Case 改写整个文件格式。"""
    if layout == "list":
        return entries
    if layout == "suite":
        return {**raw, "cases": entries}
    return entries[0] if entries else []


def _validate_case_dict(
    item: dict[str, Any], settings: Settings, *, yaml_dir: Path | None = None
) -> TestCase:
    staging = yaml_dir or (settings.uploads_dir / "_staging")
    staging.mkdir(parents=True, exist_ok=True)
    tmp = staging / f".validate-{uuid4().hex}.yaml"
    tmp.write_text(yaml.safe_dump([item], allow_unicode=True, sort_keys=False), encoding="utf-8")
    try:
        cases = load_cases(include=[str(tmp)], base_dir=settings.project_root)
    except ValidationError as exc:
        raise BenchmarkValidationError(
            format_validation_exception(exc, prefix="用例校验失败")
        ) from exc
    except Exception as exc:  # noqa: BLE001
        message = str(exc).split(": ", 1)[-1].strip()
        raise BenchmarkValidationError(
            f"用例校验失败：{message}"
            if message
            else "用例校验失败，请检查用例内容和字段格式"
        ) from exc
    finally:
        tmp.unlink(missing_ok=True)
    if len(cases) != 1:
        raise BenchmarkValidationError("用例校验失败：须恰好一条")
    return cases[0]


def _locate_case_file(benchmark: Benchmark, sample_id: str, settings: Settings) -> Path:
    cases = load_benchmark_cases(benchmark, settings=settings)
    case = next((c for c in cases if c.sample_id == sample_id), None)
    if case is None or not case.case_file:
        raise BenchmarkValidationError(f"用例 {sample_id} 不存在或未记录源文件")
    path = _storage_root(benchmark, settings) / case.case_file
    if not path.is_file():
        raise BenchmarkValidationError(f"未找到用例 {sample_id} 的源 YAML：{case.case_file}")
    return path


def export_case_yaml(
    benchmark: Benchmark, sample_id: str, *, settings: Settings | None = None
) -> tuple[str, str]:
    """导出单条用例 YAML 文本，返回 (case_file, yaml_text)。"""
    settings = settings or get_settings()
    cases = load_benchmark_cases(benchmark, settings=settings)
    case = next((c for c in cases if c.sample_id == sample_id), None)
    if case is None:
        raise BenchmarkValidationError(f"用例 {sample_id} 不存在")
    if benchmark.source == "online":
        path = _locate_case_file(benchmark, sample_id, settings)
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        entries, layout = _source_case_entries(raw)
        for entry in entries:
            if isinstance(entry, dict) and entry.get("sample_id") == sample_id:
                # defaults + cases 形式的条目可能依赖顶层默认值，导出完整校验结果。
                if layout == "suite":
                    entry = case.model_dump(mode="json")
                    entry.pop("case_file", None)
                text = yaml.safe_dump(
                    [_literalize_turn_content(entry)],
                    allow_unicode=True,
                    sort_keys=False,
                )
                return case.case_file or "", text
        raise BenchmarkValidationError(f"源文件中未找到用例 {sample_id}")
    data = case.model_dump(mode="json")
    data.pop("case_file", None)
    text = yaml.safe_dump([data], allow_unicode=True, sort_keys=False)
    return case.case_file or "", text


def save_case_yaml(
    benchmark: Benchmark,
    sample_id: str,
    yaml_text: str,
    *,
    settings: Settings | None = None,
) -> TestCase:
    """校验并写回单条用例到其源 YAML 文件（内置/上传均可）。"""
    settings = settings or get_settings()
    item = _parse_single_case_yaml(yaml_text, expected_sample_id=sample_id)
    path = _locate_case_file(benchmark, sample_id, settings)
    case = _validate_case_dict(item, settings, yaml_dir=path.parent)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries, layout = _source_case_entries(raw)
    updated: list[Any] = []
    found = False
    for entry in entries:
        if isinstance(entry, dict) and entry.get("sample_id") == sample_id:
            updated.append(item)
            found = True
        else:
            updated.append(entry)
    if not found:
        raise BenchmarkValidationError(f"源文件中未找到用例 {sample_id}")
    rebuilt = _rebuild_source_root(raw, updated, layout)
    path.write_text(
        yaml.safe_dump(rebuilt, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    _invalidate_cases_cache(benchmark.storage_path)
    return case


def delete_case(
    benchmark: Benchmark,
    sample_id: str,
    *,
    settings: Settings | None = None,
) -> list[TestCase]:
    """从上传 benchmark 的源 YAML 中删除单条 case，并返回剩余用例。"""
    settings = settings or get_settings()
    if benchmark.source == "builtin":
        raise BenchmarkValidationError("内置 benchmark 不可删除单个用例")
    path = _locate_case_file(benchmark, sample_id, settings)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries, layout = _source_case_entries(raw)

    updated: list[Any] = []
    found = False
    for entry in entries:
        if isinstance(entry, dict) and entry.get("sample_id") == sample_id:
            found = True
            continue
        updated.append(entry)
    if not found:
        raise BenchmarkValidationError(f"源文件中未找到用例 {sample_id}")

    rebuilt = _rebuild_source_root(raw, updated, layout)
    path.write_text(
        yaml.safe_dump(rebuilt, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    _invalidate_cases_cache(benchmark.storage_path)
    return load_benchmark_cases(benchmark, settings=settings)
