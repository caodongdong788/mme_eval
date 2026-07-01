"""benchmark 库：上传/校验/存储、内置注册、用例解析。

上传用例集用现有 ``medeval.loader.load_cases`` 校验（schema + 重复 sample_id），校验失败拒绝。
内置 ``cases/breast_cancer`` 注册为 ``source=builtin``。存储路径统一存绝对路径，便于 load_cases。
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from medeval.loader import load_cases
from medeval.models import TestCase

from . import feishu_base, feishu_sheet
from .models_db import Benchmark
from .settings import Settings, get_settings


class BenchmarkValidationError(Exception):
    """上传的 benchmark 用例集校验失败（schema / 解码 / 空集 / 重复 id）。"""


class _LiteralString(str):
    """YAML 输出时强制用块文本，提升线上长回复可读性。"""


_FEISHU_ROUND_LABELS = ("第一", "第二", "第三", "第四", "第五")


def _literal_representer(dumper: yaml.SafeDumper, data: _LiteralString):
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


yaml.SafeDumper.add_representer(_LiteralString, _literal_representer)


def _literal_multiline(value: str) -> str:
    return _LiteralString(value) if "\n" in value else value


def _literalize_turn_content(case: dict[str, Any]) -> dict[str, Any]:
    item = dict(case)
    turns = item.get("turns")
    if not isinstance(turns, list):
        return item
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


def _collect_score_profiles(cases: list[TestCase]) -> list[str]:
    return sorted({c.score_profile.value for c in cases})


def _collect_levels(cases: list[TestCase]) -> list[str]:
    return sorted({getattr(c.level, "value", c.level) for c in cases})


def _validate_yaml_bytes(content: bytes, settings: Settings) -> tuple[Path, list[TestCase]]:
    """把上传内容写到暂存文件并用 loader 校验。返回 (暂存路径, 用例列表)。"""
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BenchmarkValidationError(f"文件不是合法 UTF-8 文本：{exc}") from exc

    staging = settings.uploads_dir / "_staging"
    staging.mkdir(parents=True, exist_ok=True)
    tmp = staging / f"{uuid4().hex}.yaml"
    tmp.write_text(text, encoding="utf-8")
    try:
        cases = load_cases(include=[str(tmp)], base_dir=settings.project_root)
    except Exception as exc:  # noqa: BLE001 —— loader 校验失败统一转领域错误
        tmp.unlink(missing_ok=True)
        raise BenchmarkValidationError(f"用例校验失败：{exc}") from exc
    if not cases:
        tmp.unlink(missing_ok=True)
        raise BenchmarkValidationError("用例集为空或不含合法用例")
    return tmp, cases


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

    row = Benchmark(
        name=name,
        description=description,
        version=version or "v1",
        source=source,
        case_count=len(cases),
        tags=_collect_score_profiles(cases),
        levels=_collect_levels(cases),
        storage_path="",
        created_by=created_by,
    )
    session.add(row)
    session.flush()

    dest_dir = settings.uploads_dir / str(row.id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / _safe_yaml_name(filename)
    tmp.replace(dest)
    row.storage_path = str(dest_dir)
    return row


def online_jsonl_to_yaml_bytes(content: bytes) -> bytes:
    """把线上真实对话 JSONL 转为标准 benchmark YAML。

    线上文件每行是一条 Q&A，核心字段为「用户输入内容」和「Cx输出内容」。
    转换后仍复用 TestCase schema：user/assistant 两轮作为一条完整 Q&A 留存，
    `source=online` 便于列表和后续评测链路区分真实流量。
    """
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise BenchmarkValidationError(f"文件不是合法 UTF-8 文本：{exc}") from exc

    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise BenchmarkValidationError(f"JSONL 第 {line_no} 行解析失败：{exc}") from exc
        if not isinstance(row, dict):
            raise BenchmarkValidationError(f"JSONL 第 {line_no} 行须为对象")

        question = str(row.get("用户输入内容") or "").strip()
        answer = str(row.get("Cx输出内容") or "").strip()
        if not question or not answer:
            raise BenchmarkValidationError(
                f"JSONL 第 {line_no} 行缺少「用户输入内容」或「Cx输出内容」"
            )

        sample_id = _unique_online_sample_id(seen, row.get("序号"), line_no)

        title = str(row.get("会话标题") or "").strip()
        cases.append({
            "sample_id": sample_id,
            "scenario": "线上真实对话",
            "sub_scenario": title or sample_id,
            "level": "L2",
            "score_profile": "default",
            "source": "online",
            "turns": [
                {"role": "user", "content": _literal_multiline(question)},
                {"role": "assistant", "content": _literal_multiline(answer)},
            ],
        })

    if not cases:
        raise BenchmarkValidationError("JSONL 中没有可转换的线上 Q&A")
    return yaml.safe_dump(cases, allow_unicode=True, sort_keys=False).encode("utf-8")


def feishu_base_records_to_yaml_bytes(records: list[dict[str, Any]]) -> bytes:
    """把飞书 Base 记录转为线上 benchmark YAML，完整保留每轮对话。"""
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, record in enumerate(records, start=1):
        fields = record.get("fields") if isinstance(record, dict) else {}
        if not isinstance(fields, dict):
            continue
        turns: list[dict[str, str]] = []
        for round_label in _FEISHU_ROUND_LABELS:
            user = _cell_text(fields.get(f"{round_label}轮用户输入"))
            assistant = _cell_text(fields.get(f"{round_label}轮Cx输出"))
            if user:
                turns.append({"role": "user", "content": _literal_multiline(user)})
            if assistant:
                turns.append({"role": "assistant", "content": _literal_multiline(assistant)})
        if not turns:
            continue

        sample_id = _unique_online_sample_id(seen, record.get("record_id"), index)

        title = _cell_text(fields.get("会话标题"))
        case: dict[str, Any] = {
            "sample_id": sample_id,
            "scenario": "线上真实对话",
            "sub_scenario": title or sample_id,
            "level": "L2",
            "score_profile": "default",
            "source": "online",
            "turns": turns,
        }
        image_notes = _attachment_notes(fields.get("第一轮用户输入(图片)"))
        if image_notes:
            case["notes"] = f"第一轮用户输入(图片)：{image_notes}"
        cases.append(case)

    if not cases:
        raise BenchmarkValidationError("飞书 Base 中没有可转换的线上对话")
    return yaml.safe_dump(cases, allow_unicode=True, sort_keys=False).encode("utf-8")


def feishu_sheet_cells_to_yaml_bytes(sheet: dict[str, Any]) -> bytes:
    """把飞书 Sheet 单元格转为线上 benchmark YAML，保留多轮文本与图片 token。"""
    cells = sheet.get("cells") or []
    row_indices = sheet.get("row_indices") or []
    if not cells or not isinstance(cells, list):
        raise BenchmarkValidationError("飞书 Sheet 中没有可转换的线上对话")

    headers = [_cell_text(cell) for cell in cells[0]]
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, row in enumerate(cells[1:], start=1):
        if not isinstance(row, list):
            continue
        fields = {
            headers[col_index]: cell
            for col_index, cell in enumerate(row)
            if col_index < len(headers) and headers[col_index]
        }
        turns: list[dict[str, str]] = []
        for round_label in _FEISHU_ROUND_LABELS:
            user_cell = fields.get(f"{round_label}轮用户输入")
            assistant_cell = fields.get(f"{round_label}轮Cx输出")
            user = _cell_text(user_cell)
            assistant = _cell_text(assistant_cell)
            if user:
                turns.append({"role": "user", "content": _literal_multiline(user)})
            if assistant:
                turns.append({"role": "assistant", "content": _literal_multiline(assistant)})
        if not turns:
            continue

        row_number = row_indices[index] if index < len(row_indices) else index + 1
        raw_id = f"{sheet.get('sheet_name') or sheet.get('sheet_id') or 'sheet'}_{row_number}"
        sample_id = _unique_online_sample_id(seen, raw_id, index)
        title = _cell_text(fields.get("会话标题"))
        case: dict[str, Any] = {
            "sample_id": sample_id,
            "scenario": "线上真实对话",
            "sub_scenario": title or sample_id,
            "level": "L2",
            "score_profile": "default",
            "source": "online",
            "turns": turns,
        }
        cases.append(case)

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
            sheet = feishu_sheet.fetch_sheet_cells(access_token, source_url)
        except feishu_sheet.FeishuSheetError as exc:
            raise BenchmarkValidationError(str(exc)) from exc
        return feishu_sheet_cells_to_yaml_bytes(sheet)
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
        settings=settings,
    )


def _replace_uploaded_benchmark_with_yaml_bytes(
    session: Session,
    benchmark: Benchmark,
    *,
    yaml_content: bytes,
    filename: str,
    source: str,
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
    benchmark.tags = _collect_score_profiles(cases)
    benchmark.levels = _collect_levels(cases)
    benchmark.storage_path = str(dest_dir)
    benchmark.source = source
    _invalidate_cases_cache(benchmark.storage_path)
    return benchmark


def replace_uploaded_benchmark_from_feishu_url(
    session: Session,
    benchmark: Benchmark,
    *,
    source_url: str,
    access_token: str,
    settings: Settings | None = None,
) -> Benchmark:
    yaml_content = feishu_url_to_yaml_bytes(access_token, source_url)
    return _replace_uploaded_benchmark_with_yaml_bytes(
        session,
        benchmark,
        yaml_content=yaml_content,
        filename=f"{benchmark.name}.yaml",
        source="online",
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
    settings: Settings | None = None,
) -> Benchmark:
    """校验并保存一个上传的 benchmark；校验失败抛 BenchmarkValidationError。"""
    settings = settings or get_settings()
    name = (name or "").strip() or "未命名 benchmark"
    source = source if source in {"online", "offline"} else "offline"
    yaml_content = online_jsonl_to_yaml_bytes(content) if source == "online" else content
    return _create_uploaded_benchmark_from_yaml_bytes(
        session,
        name=name,
        yaml_content=yaml_content,
        filename=filename if source == "offline" else f"{name}.yaml",
        description=description,
        version=version or "v1",
        source=source,
        created_by=created_by,
        settings=settings,
    )


# 允许通过派生覆盖的 case 判据字段（仅判分相关，不含会话/元数据）。
_CASE_OVERRIDE_FIELDS = ("expected_behavior", "hard_gates", "rubric", "scoring_points")


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
            raise BenchmarkValidationError(f"用例 {sid} 判据非法：{exc}") from exc
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
    return create_uploaded_benchmark(
        session,
        name=name,
        content=text.encode("utf-8"),
        filename=f"{name}.yaml",
        description=description,
        created_by=created_by,
        settings=settings,
    )


def _yaml_to_case_overrides(yaml_text: str) -> list[dict[str, Any]]:
    """把整段用例 YAML 解析成判据覆盖列表（按 sample_id 取判据字段，其余忽略）。

    顶层须为用例 dict 列表；无任何带 sample_id 的用例时抛 BenchmarkValidationError。
    """
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        raise BenchmarkValidationError(f"YAML 解析失败：{exc}") from exc
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
    """若内置 benchmark 尚未注册则创建（指向仓库 cases 目录）。幂等。"""
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
        existing.tags = _collect_score_profiles(cases)
        existing.levels = _collect_levels(cases)
        session.flush()
        return existing

    if not cases:
        return None
    row = Benchmark(
        name="乳腺癌专科 benchmark",
        description="内置乳腺癌全病程套件（cases/breast_cancer）",
        version="v1",
        source="builtin",
        case_count=len(cases),
        tags=_collect_score_profiles(cases),
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
    settings: Settings | None = None,
) -> Benchmark:
    """用新内容覆盖一个已上传的 benchmark（保留 id/name）。builtin 不可覆盖。"""
    settings = settings or get_settings()
    if benchmark.source == "builtin":
        raise BenchmarkValidationError("内置 benchmark 不可覆盖")
    next_source = source if source in {"online", "offline"} else benchmark.source
    next_source = next_source if next_source in {"online", "offline"} else "offline"
    yaml_content = online_jsonl_to_yaml_bytes(content) if next_source == "online" else content
    return _replace_uploaded_benchmark_with_yaml_bytes(
        session,
        benchmark,
        yaml_content=yaml_content,
        filename=filename if next_source == "offline" else f"{benchmark.name}.yaml",
        source=next_source,
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


# 用例解析结果缓存：键 = (storage_path, mtime, score_profiles)；mtime 变更（覆盖/替换）自动失效。
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
    score_profiles: list[str] | None = None,
    settings: Settings | None = None,
) -> list[TestCase]:
    """加载某 benchmark 的用例（可按 score_profile 过滤）。

    按 ``(storage_path, mtime, score_profiles)`` 做进程内缓存，避免发起页/重判反复读盘解析 YAML；
    文件被覆盖（mtime 变化）即自动失效。返回深拷贝以隔离调用方的就地修改。
    """
    settings = settings or get_settings()
    profiles = tuple(score_profiles or [])
    mtime = _path_mtime(benchmark.storage_path, settings)
    key = (benchmark.storage_path, mtime, profiles)
    if mtime is not None:
        cached = _CASES_CACHE.get(key)
        if cached is not None:
            return [c.model_copy(deep=True) for c in cached]
    cases = load_cases(
        include=[benchmark.storage_path],
        score_profiles=list(profiles),
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
        raise BenchmarkValidationError(f"YAML 解析失败：{exc}") from exc
    if not isinstance(data, list) or len(data) != 1:
        raise BenchmarkValidationError("YAML 须为仅含一条用例的列表")
    item = data[0]
    if not isinstance(item, dict):
        raise BenchmarkValidationError("用例须为 mapping")
    sid = str(item.get("sample_id") or "").strip()
    if sid != expected_sample_id:
        raise BenchmarkValidationError(f"sample_id 须为 {expected_sample_id}，实际为 {sid or '(空)'}")
    return item


def _validate_case_dict(item: dict[str, Any], settings: Settings) -> TestCase:
    staging = settings.uploads_dir / "_staging"
    staging.mkdir(parents=True, exist_ok=True)
    tmp = staging / f"{uuid4().hex}.yaml"
    tmp.write_text(yaml.safe_dump([item], allow_unicode=True, sort_keys=False), encoding="utf-8")
    try:
        cases = load_cases(include=[str(tmp)], base_dir=settings.project_root)
    except Exception as exc:  # noqa: BLE001
        raise BenchmarkValidationError(f"用例校验失败：{exc}") from exc
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
        if not isinstance(raw, list):
            raise BenchmarkValidationError("源 YAML 须为用例列表")
        for entry in raw:
            if isinstance(entry, dict) and entry.get("sample_id") == sample_id:
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
    case = _validate_case_dict(item, settings)
    path = _locate_case_file(benchmark, sample_id, settings)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise BenchmarkValidationError("源 YAML 须为用例列表")
    updated: list[Any] = []
    found = False
    for entry in raw:
        if isinstance(entry, dict) and entry.get("sample_id") == sample_id:
            updated.append(item)
            found = True
        else:
            updated.append(entry)
    if not found:
        raise BenchmarkValidationError(f"源文件中未找到用例 {sample_id}")
    path.write_text(
        yaml.safe_dump(updated, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    _invalidate_cases_cache(benchmark.storage_path)
    return case
