"""解析飞书 benchmark 表格行 → 结构化 RawRow。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# 固定列（与业务表格一致）
COL_TEST_CONTENT = "测试内容"
COL_SCORING_POINTS = "得分点明细"
COL_ROUND_COUNT = "轮数"

FIXED_HEADERS = (COL_TEST_CONTENT, COL_SCORING_POINTS, COL_ROUND_COUNT)

_ROUND_COL_RE = re.compile(r"^第\s*(\d+)\s*轮", re.IGNORECASE)
_SCORING_LINE_RE = re.compile(r"^\s*(\d+)\s*[.、．)\]]\s*(.+)$")
_NEGATIVE_MARKERS = ("负分", "惩罚", "（负）", "(负)", "扣分")


@dataclass
class RoundDialogue:
    round_no: int
    user_text: str
    bot_reference: str


@dataclass
class RawRow:
    row_index: int  # 1-based sheet row number (for reporting)
    test_content: str
    scoring_points_text: str
    round_count_declared: int | None
    rounds: list[RoundDialogue] = field(default_factory=list)


def _norm_header(cell: str) -> str:
    return (cell or "").strip().replace("\n", "")


def _header_map(header_row: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    round_cols: list[tuple[int, int]] = []
    for idx, raw in enumerate(header_row):
        h = _norm_header(raw)
        if not h:
            continue
        m = _ROUND_COL_RE.match(h)
        if m:
            round_cols.append((int(m.group(1)), idx))
            continue
        mapping[h] = idx
    for n, idx in sorted(round_cols, key=lambda x: x[0]):
        mapping[f"__round_{n}"] = idx
    return mapping


def _cell(row: list[str], idx: int | None) -> str:
    if idx is None or idx >= len(row):
        return ""
    return (row[idx] or "").strip()


def parse_round_dialogue(cell: str) -> tuple[str, str]:
    """从「第N轮」单元格拆出用户问句与 Bot 参考回复。"""
    text = (cell or "").strip()
    if not text:
        return "", ""

    bot_split = re.split(r"(?im)^Bot\s*[：:]\s*", text, maxsplit=1)
    if len(bot_split) == 2:
        before_bot, bot_ref = bot_split[0], bot_split[1].strip()
    else:
        before_bot, bot_ref = text, ""

    user_split = re.split(r"(?im)^用户\s*[：:]\s*", before_bot, maxsplit=1)
    if len(user_split) == 2:
        user_text = user_split[1].strip()
    else:
        user_text = before_bot.strip()
        # 去掉可能残留的「用户：」前缀
        user_text = re.sub(r"(?im)^用户\s*[：:]\s*", "", user_text).strip()

    return user_text, bot_ref


def parse_scoring_points(text: str) -> list[dict[str, object]]:
    """把「得分点明细」单元格解析为 scoring_points 字段 dict 列表。"""
    raw = (text or "").strip()
    if not raw:
        return []

    items: list[tuple[int, str]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _SCORING_LINE_RE.match(line)
        if m:
            items.append((int(m.group(1)), m.group(2).strip()))
        elif not items:
            # 无编号的首行当作第 1 条
            items.append((1, line))
        else:
            # 续行拼到上一条
            prev_n, prev_t = items[-1]
            items[-1] = (prev_n, f"{prev_t} {line}")

    if not items and raw:
        items.append((1, raw))

    result: list[dict[str, object]] = []
    for _n, body in items:
        negative = any(marker in body for marker in _NEGATIVE_MARKERS)
        criterion = body
        for marker in ("（负分/惩罚）", "（负分）", "(负分/惩罚)", "(负分)", "（负分/惩罚）"):
            criterion = criterion.replace(marker, "")
        criterion = re.sub(r"[（(]\s*负分\s*[/／]\s*惩罚\s*[）)]", "", criterion)
        criterion = re.sub(r"[（(]\s*惩罚\s*[）)]", "", criterion).strip()
        points = -3 if negative else 3
        entry: dict[str, object] = {"criterion": criterion, "points": points}
        if not negative:
            entry["critical"] = True
        result.append(entry)
    return result


def _parse_round_count(value: str) -> int | None:
    v = (value or "").strip()
    if not v:
        return None
    try:
        return int(float(v))
    except ValueError:
        return None


def parse_sheet_rows(values: list[list[str]]) -> list[RawRow]:
    """把 lark-cli +read 的 values 二维数组解析为 RawRow 列表。"""
    if not values:
        return []

    header = values[0]
    hmap = _header_map(header)

    missing = [c for c in FIXED_HEADERS if c not in hmap]
    if missing:
        raise ValueError(
            f"表头缺少必需列: {missing}；当前表头: {[ _norm_header(c) for c in header ]}"
        )

    round_keys = sorted(
        (int(k.split("_")[-1]), k) for k in hmap if k.startswith("__round_")
    )
    if not round_keys:
        raise ValueError("表头未找到「第N轮 (用户+Bot)」列")

    rows: list[RawRow] = []
    for row_idx, row in enumerate(values[1:], start=2):
        rounds: list[RoundDialogue] = []
        for n, key in round_keys:
            cell = _cell(row, hmap.get(key))
            if not cell:
                continue
            user_text, bot_ref = parse_round_dialogue(cell)
            if not user_text and not bot_ref:
                continue
            rounds.append(
                RoundDialogue(round_no=n, user_text=user_text, bot_reference=bot_ref)
            )
        if not rounds:
            continue

        raw = RawRow(
            row_index=row_idx,
            test_content=_cell(row, hmap.get(COL_TEST_CONTENT)),
            scoring_points_text=_cell(row, hmap.get(COL_SCORING_POINTS)),
            round_count_declared=_parse_round_count(
                _cell(row, hmap.get(COL_ROUND_COUNT))
            ),
            rounds=rounds,
        )
        rows.append(raw)
    return rows
