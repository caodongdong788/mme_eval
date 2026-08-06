"""transcripts.xlsx 的**纯内容派生层**（无 openpyxl 依赖、无副作用）。

参见 OpenSpec change ``2026-06-02-split-transcript-cells``：把"单元格文本怎么算"
（截断 / CJK 折行估算 / 维度比率）从排版写入层
（``excel_transcript.py``）拆出，让这些逻辑可独立单测。

这里只接受已解析好的数据。
"""

from __future__ import annotations

import math

from ..evaluation import DIMENSION_LABELS, EvaluationDimension
from ..models import CaseResult

# openpyxl 单 cell 上限（Excel 规范）
_MAX_CELL_LEN = 32_767
_TRUNCATE_NOTICE = "…（已截断，完整内容见 report.json 中对应 trace）"

# 命中关键词的纯文本标记（飞书在线表格可正常显示）。
_MARK_L, _MARK_R = "【", "】"

def _display_lines(text: str, width_units: int) -> int:
    """估算一段文本在指定列宽下换行后占多少行（中文按 2 个单位宽计）。"""
    lines = 0
    for seg in text.split("\n"):
        if not seg:
            lines += 1
            continue
        weighted = sum(2 if ord(ch) > 0x2E80 else 1 for ch in seg)
        lines += max(1, math.ceil(weighted / width_units))
    return lines


def _truncate(s: str) -> str:
    if len(s) <= _MAX_CELL_LEN:
        return s
    return s[: _MAX_CELL_LEN - len(_TRUNCATE_NOTICE)] + _TRUNCATE_NOTICE


def _user_turn_count(case_result: CaseResult) -> int:
    """对话深度 = case 中 user role 轮数。"""
    return sum(1 for m in case_result.trace.messages if m.role == "user")


def _turns(case_result: CaseResult) -> list[tuple[str, str | None, float | None]]:
    """把一条 trace 折叠成按轮次的 (用户输入, bot回复, 该轮耗时ms) 列表。

    * system 消息不计入轮次（系统提示词不属于对话流水）。
    * 每个 user 消息开启一轮，紧随的 assistant 消息为该轮 bot 回复。
    * 末轮失败（无 assistant）时 bot 记 None。
    * 逐轮耗时按 ``trace.turn_latencies_ms`` 顺序分配给"有 bot 回复"的轮次，
      代表「用户发出 → bot 首个响应」的端到端耗时。
    """
    latencies = list(case_result.trace.turn_latencies_ms)
    li = 0
    pairs: list[tuple[str, str | None, float | None]] = []
    pending_user: str | None = None
    for msg in case_result.trace.messages:
        if msg.role == "system":
            continue
        if msg.role == "user":
            if pending_user is not None:
                pairs.append((pending_user, None, None))
            pending_user = msg.content
        else:  # assistant / bot
            lat = latencies[li] if li < len(latencies) else None
            li += 1
            pairs.append((pending_user or "", msg.content, lat))
            pending_user = None
    if pending_user is not None:
        pairs.append((pending_user, None, None))
    return pairs


def _case_title(result: CaseResult) -> str:
    """用例描述行：场景为空时回退到 sample_id。"""
    c = result.case
    return c.scenario or c.sample_id


def _test_content_cell(result: CaseResult) -> str:
    """测试内容列：描述 + 来源文件名。"""
    case = result.case
    lines = [_case_title(result)]
    if case.case_file:
        lines.append(case.case_file)
    return "\n".join(lines)


def _deduction_text(result: CaseResult) -> str:
    """扣分原因列：展开低分维度理由及指南、门禁等额外扣分。"""
    by_name = {verdict.name: verdict for verdict in result.verdicts}
    reasons: list[str] = []
    for dimension in EvaluationDimension:
        verdict = by_name.get(f"dimension.{dimension.value}")
        if verdict is None:
            continue
        score = float(
            result.dimension_raw_scores.get(dimension.value, verdict.score)
        )
        if score >= 5:
            continue
        reason = verdict.reason.strip() or "未提供判定理由"
        reasons.append(
            f"{DIMENSION_LABELS[dimension]} {score:g}/5：{reason}"
        )

    reasons.extend(result.score_deductions)
    reasons = list(dict.fromkeys(reasons))
    if not reasons:
        return "—"
    return _truncate("\n".join(reasons))


def _highlight_runs(text: str, keywords: list[str]) -> list[tuple[str, bool]]:
    """把 text 切成 (片段, 是否命中) 列表；命中任一 keyword 的子串标记。

    大小写不敏感、合并重叠区间；无命中时返回单段 (text, False)。
    """
    spans: list[tuple[int, int]] = []
    low = text.lower()
    for kw in keywords:
        if not kw:
            continue
        k = kw.lower()
        start = 0
        while True:
            i = low.find(k, start)
            if i < 0:
                break
            spans.append((i, i + len(kw)))
            start = i + len(kw)
    if not spans:
        return [(text, False)]
    spans.sort()
    merged: list[list[int]] = []
    for s, e in spans:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    runs: list[tuple[str, bool]] = []
    pos = 0
    for s, e in merged:
        if s > pos:
            runs.append((text[pos:s], False))
        runs.append((text[s:e], True))
        pos = e
    if pos < len(text):
        runs.append((text[pos:], False))
    return runs


def _mark_plain(text: str, keywords: list[str]) -> str:
    """命中关键词用 ``【】`` 括起（纯文本，飞书/Excel 通用）。"""
    runs = _highlight_runs(text, keywords)
    if not any(hit for _, hit in runs):
        return text
    return "".join(f"{_MARK_L}{seg}{_MARK_R}" if hit else seg for seg, hit in runs)


def _turn_cell(user: str, bot: str | None, keywords: list[str]) -> str:
    """构造一轮的纯文本 cell；命中关键词用 ``【】`` 标记（飞书/Excel 通用）。"""
    bot_text = bot if bot is not None else "（无回复）"
    head = f"👤 用户：{user}\n\n🤖 Bot："

    if bot is None or not keywords or len(head) + len(bot_text) > _MAX_CELL_LEN:
        return _truncate(head + bot_text)
    return _truncate(head + _mark_plain(bot_text, keywords))
