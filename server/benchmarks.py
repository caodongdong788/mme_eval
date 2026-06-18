"""benchmark 库：上传/校验/存储、内置注册、用例解析。

上传用例集用现有 ``medeval.loader.load_cases`` 校验（schema + 重复 sample_id），校验失败拒绝。
内置 ``cases/breast_cancer`` 注册为 ``source=builtin``。存储路径统一存绝对路径，便于 load_cases。
"""

from __future__ import annotations

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

from .models_db import Benchmark
from .settings import Settings, get_settings


class BenchmarkValidationError(Exception):
    """上传的 benchmark 用例集校验失败（schema / 解码 / 空集 / 重复 id）。"""


def _safe_yaml_name(filename: str) -> str:
    name = Path(filename or "").name or "cases.yaml"
    if not name.endswith((".yaml", ".yml")):
        name = name + ".yaml"
    name = re.sub(r"[^A-Za-z0-9_.\-]", "_", name)
    return name


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


def create_uploaded_benchmark(
    session: Session,
    *,
    name: str,
    content: bytes,
    filename: str = "cases.yaml",
    description: str = "",
    version: str = "v1",
    created_by: str | None = None,
    settings: Settings | None = None,
) -> Benchmark:
    """校验并保存一个上传的 benchmark；校验失败抛 BenchmarkValidationError。"""
    settings = settings or get_settings()
    name = (name or "").strip() or "未命名 benchmark"
    existing = session.execute(
        select(Benchmark).where(Benchmark.name == name)
    ).scalars().first()
    if existing is not None:
        raise BenchmarkValidationError(f"benchmark 名称「{name}」已存在，请换一个名称")
    tmp, cases = _validate_yaml_bytes(content, settings)

    row = Benchmark(
        name=name,
        description=description,
        version=version or "v1",
        source="uploaded",
        case_count=len(cases),
        tags=_collect_score_profiles(cases),
        levels=_collect_levels(cases),
        storage_path="",
        created_by=created_by,
    )
    session.add(row)
    session.flush()  # 取得 row.id 以建目录

    dest_dir = settings.uploads_dir / str(row.id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / _safe_yaml_name(filename)
    tmp.replace(dest)
    row.storage_path = str(dest_dir)
    return row


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
    settings: Settings | None = None,
) -> Benchmark:
    """用新内容覆盖一个已上传的 benchmark（保留 id/name）。builtin 不可覆盖。"""
    settings = settings or get_settings()
    if benchmark.source == "builtin":
        raise BenchmarkValidationError("内置 benchmark 不可覆盖")
    tmp, cases = _validate_yaml_bytes(content, settings)

    dest_dir = settings.uploads_dir / str(benchmark.id)
    shutil.rmtree(dest_dir, ignore_errors=True)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / _safe_yaml_name(filename)
    tmp.replace(dest)

    benchmark.case_count = len(cases)
    benchmark.tags = _collect_score_profiles(cases)
    benchmark.levels = _collect_levels(cases)
    benchmark.storage_path = str(dest_dir)
    return benchmark


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
