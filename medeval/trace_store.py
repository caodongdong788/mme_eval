"""会话留痕落盘 / 读回（参见 OpenSpec change persist-traces-rejudge）。

借鉴 OpenCompass `Inference → Evaluation` 解耦范式：把每条用例的全部 N-runs
``ConversationTrace`` 作为一等产物落盘，支撑离线重判（rejudge）与断点续跑（resume）。

落盘格式：``traces.jsonl.gz``（gzip + jsonl，零第三方依赖）。
  * 首行 meta：``{"_meta": {schema, adapter_fingerprint, store_raw, n_runs, n_cases}}``
  * 其后每行一条：``{"sample_id", "case_index", "run_idx", "trace": {...}}``

run 阶段先增量写未压缩的 ``traces.partial.jsonl``（崩溃也留得下已完成部分），
run 阶段整体结束后 ``finalize_traces`` 压缩成 ``traces.jsonl.gz`` 并删 partial。

``store_raw`` 在**写入时**对 ``raw_responses`` 瘦身（never/on_error/always）。
"""

from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any, Sequence

from .models import ChatMessage, ConversationTrace, TestCase

__all__ = [
    "SCHEMA_VERSION",
    "TRACES_GZ",
    "PARTIAL",
    "ChatMessage",
    "ConversationTrace",
    "trim_raw_responses",
    "adapter_fingerprint",
    "PartialTraceWriter",
    "finalize_traces",
    "write_traces",
    "read_traces",
    "TracesBundle",
]

SCHEMA_VERSION = 1
TRACES_GZ = "traces.jsonl.gz"
PARTIAL = "traces.partial.jsonl"


# ---------------------------------------------------------------------------
# store_raw 瘦身
# ---------------------------------------------------------------------------


def trim_raw_responses(trace: ConversationTrace, store_raw: str) -> ConversationTrace:
    """按 store_raw 档位裁剪 ``raw_responses``，返回（可能是新的）trace。

    只动 ``raw_responses``，``messages``/``turn_latencies_ms``/``error`` 等离线重判
    所需字段一律保留。
    """
    if store_raw == "always":
        return trace
    if store_raw == "never":
        return trace.model_copy(update={"raw_responses": []})
    # on_error：仅在该留痕报错时保留全量 raw，成功轮次清空
    if trace.error:
        return trace
    return trace.model_copy(update={"raw_responses": []})


# ---------------------------------------------------------------------------
# adapter 指纹（续跑安全闸：排除 api_key 等密钥）
# ---------------------------------------------------------------------------


def _strip_secrets(obj: Any) -> Any:
    """递归剔除疑似密钥字段（api_key），其余结构原样保留。"""
    if isinstance(obj, dict):
        return {
            k: _strip_secrets(v)
            for k, v in obj.items()
            if k not in ("api_key",)
        }
    if isinstance(obj, list):
        return [_strip_secrets(v) for v in obj]
    return obj


def adapter_fingerprint(adapter_type: str, adapter_config: dict[str, Any]) -> str:
    """被测 bot 的指纹（12 位 sha1）：type + 配置（剔除 api_key）。

    续跑时用于拒绝把不同 bot 的旧留痕混入本次结果。api_key 等密钥不影响指纹，
    使「换了 key 但同一 bot」仍可续跑。
    """
    blob = json.dumps(
        {"type": adapter_type, "config": _strip_secrets(adapter_config or {})},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------------------
# 记录序列化
# ---------------------------------------------------------------------------


def _record_line(sample_id: str, case_index: int, run_idx: int, trace: ConversationTrace) -> str:
    return json.dumps(
        {
            "sample_id": sample_id,
            "case_index": case_index,
            "run_idx": run_idx,
            "trace": trace.model_dump(mode="json"),
        },
        ensure_ascii=False,
    )


def _meta_line(meta: dict[str, Any]) -> str:
    return json.dumps({"_meta": meta}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 增量写 + finalize
# ---------------------------------------------------------------------------


class PartialTraceWriter:
    """run 阶段增量写 ``traces.partial.jsonl``（未压缩、可 append）。

    每完成一个 (sample_id, run_idx) 调一次 ``record``；按 store_raw 在写入时瘦身。
    单进程 asyncio / ray driver 单线程顺序回调，无需额外加锁。
    """

    def __init__(self, out_dir: Path, *, store_raw: str, meta: dict[str, Any]):
        self.out_dir = Path(out_dir)
        self.store_raw = store_raw
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._path = self.out_dir / PARTIAL
        self._fh: IO[str] = self._path.open("w", encoding="utf-8")
        self._fh.write(_meta_line(meta) + "\n")
        self._fh.flush()

    def record(self, sample_id: str, case_index: int, run_idx: int, trace: ConversationTrace) -> None:
        trimmed = trim_raw_responses(trace, self.store_raw)
        self._fh.write(_record_line(sample_id, case_index, run_idx, trimmed) + "\n")
        self._fh.flush()

    def close(self) -> None:
        try:
            self._fh.close()
        except Exception:  # pragma: no cover
            pass


def finalize_traces(out_dir: Path) -> Path | None:
    """把 ``traces.partial.jsonl`` 压缩为 ``traces.jsonl.gz`` 并删 partial。

    无 partial 时返回 None（例如未开启落盘）。
    """
    out_dir = Path(out_dir)
    partial = out_dir / PARTIAL
    if not partial.exists():
        return None
    gz = out_dir / TRACES_GZ
    with partial.open("rb") as src, gzip.open(gz, "wb") as dst:
        dst.write(src.read())
    partial.unlink(missing_ok=True)
    return gz


def write_traces(
    out_dir: Path,
    cases: Sequence[TestCase],
    per_case_traces: Sequence[Sequence[ConversationTrace]],
    *,
    store_raw: str,
    meta: dict[str, Any],
) -> Path:
    """一次性把全部留痕写成 ``traces.jsonl.gz``（非流式路径 / 测试用）。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    gz = out_dir / TRACES_GZ
    with gzip.open(gz, "wt", encoding="utf-8") as fh:
        fh.write(_meta_line(meta) + "\n")
        for case_index, (case, runs) in enumerate(zip(cases, per_case_traces)):
            for run_idx, trace in enumerate(runs):
                trimmed = trim_raw_responses(trace, store_raw)
                fh.write(_record_line(case.sample_id, case_index, run_idx, trimmed) + "\n")
    return gz


# ---------------------------------------------------------------------------
# 读回
# ---------------------------------------------------------------------------


@dataclass
class TracesBundle:
    meta: dict[str, Any]
    by_key: dict[tuple[str, int], ConversationTrace] = field(default_factory=dict)

    def per_case_traces(
        self, cases: Sequence[TestCase], n_runs: int
    ) -> list[list[ConversationTrace]]:
        """按给定用例顺序与 n_runs 重建 ``list[list[ConversationTrace]]``。

        缺失的 (sample_id, run_idx) 跳过（内层只含实际存在的留痕，按 run_idx 升序）。
        """
        out: list[list[ConversationTrace]] = []
        for case in cases:
            runs: list[ConversationTrace] = []
            for run_idx in range(max(1, n_runs)):
                t = self.by_key.get((case.sample_id, run_idx))
                if t is not None:
                    runs.append(t)
            out.append(runs)
        return out


def _iter_lines(run_dir: Path) -> tuple[Path, bool] | None:
    """定位留痕文件：优先 .gz，其次残留 partial。返回 (path, is_gzip) 或 None。"""
    gz = run_dir / TRACES_GZ
    if gz.exists():
        return gz, True
    partial = run_dir / PARTIAL
    if partial.exists():
        return partial, False
    return None


def read_traces(run_dir: Path) -> TracesBundle | None:
    """读回留痕（优先 .gz，回退残留 partial）。两者皆无时返回 None。"""
    run_dir = Path(run_dir)
    located = _iter_lines(run_dir)
    if located is None:
        return None
    path, is_gzip = located
    opener = (lambda: gzip.open(path, "rt", encoding="utf-8")) if is_gzip else (
        lambda: path.open("r", encoding="utf-8")
    )
    meta: dict[str, Any] = {}
    by_key: dict[tuple[str, int], ConversationTrace] = {}
    with opener() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if "_meta" in obj:
                meta = obj["_meta"]
                continue
            trace = ConversationTrace.model_validate(obj["trace"])
            by_key[(obj["sample_id"], int(obj["run_idx"]))] = trace
    return TracesBundle(meta=meta, by_key=by_key)
