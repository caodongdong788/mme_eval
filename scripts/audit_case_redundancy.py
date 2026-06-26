"""审计 must_have 正则 与 scoring_points 之间的语义冗余（只读，不改用例）。

背景：同一医学意图常被写三遍——脆弱的 ``must_have`` 邻近正则 + ``scoring_point``
criterion + ``rubric`` 维度。正则一脆就漏判、逼出语义裁决兜底，且三处需同步维护、
易漂移。本脚本只**标记疑似重复**，供人工（须临床判断）决定是否把医学语义要点
从 must_have 下沉到 scoring_points，让 Rule 只留确定性禁词 / 结构断言。

判定启发式（保守、宁缺毋滥）：
  * 从 must_have 正则里抽出 **中文 token**（剥掉 ``.{0,n}`` / 分组 / 转义等元字符，
    按非中文切分），与每个 scoring_point.criterion 的中文 bigram 集合算重叠率。
  * 重叠率 ≥ 阈值（默认 0.5）即记为「疑似重复」。

用法：
    python scripts/audit_case_redundancy.py [cases_dir] [--threshold 0.5]

退出码恒为 0（纯报告，不做门禁，避免阻断 CI）。
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from medeval.loader import load_cases

# 正则元字符 / 量词 / 分组：抽取语义 token 前先剔除
_META = re.compile(r"\\.|[.*+?^$()\[\]{}|]|\{[0-9,]*\}")
_CJK = re.compile(r"[一-鿿]+")


def _regex_terms(pattern: str) -> list[str]:
    """从正则里抽出中文连续片段（去元字符后按非中文切分）。"""
    stripped = _META.sub(" ", pattern)
    return [t for t in _CJK.findall(stripped) if len(t) >= 2]


def _bigrams(text: str) -> set[str]:
    cjk = "".join(_CJK.findall(text))
    return {cjk[i : i + 2] for i in range(len(cjk) - 1)} if len(cjk) >= 2 else set()


def _overlap(terms: list[str], criterion: str) -> float:
    """terms 的 bigram 命中 criterion bigram 的比例（terms 为分子基准）。"""
    crit = _bigrams(criterion)
    if not crit:
        return 0.0
    term_bg: set[str] = set()
    for t in terms:
        term_bg |= _bigrams(t)
    if not term_bg:
        return 0.0
    return len(term_bg & crit) / len(term_bg)


def audit(cases_dir: Path, threshold: float) -> list[str]:
    cases = load_cases([str(cases_dir.name)], base_dir=cases_dir.parent)
    findings: list[str] = []
    for case in cases:
        mh = case.expected_behavior.must_have
        sps = case.scoring_points
        if not mh or not sps:
            continue
        for i, p in enumerate(mh):
            pat = p.regex or p.keyword or ""
            terms = _regex_terms(pat)
            if not terms:
                continue
            for j, sp in enumerate(sps):
                ov = _overlap(terms, sp.criterion)
                if ov >= threshold:
                    findings.append(
                        f"{case.case_file}  {case.sample_id}: "
                        f"must_have[{i}] 与 scoring_point[{j}] 疑似重复 "
                        f"(重叠 {ov:.0%})\n"
                        f"    正则 {pat}\n"
                        f"    得分点 {sp.criterion}"
                    )
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cases_dir", nargs="?", default="cases", type=Path)
    ap.add_argument("--threshold", type=float, default=0.5)
    args = ap.parse_args()

    if not args.cases_dir.exists():
        print(f"[audit_case_redundancy] 目录不存在: {args.cases_dir}")
        return 0

    findings = audit(args.cases_dir, args.threshold)
    if not findings:
        print(
            f"[audit_case_redundancy] ✓ 未发现重叠 ≥ {args.threshold:.0%} 的"
            " must_have / scoring_point 对"
        )
        return 0
    print(
        f"[audit_case_redundancy] 发现 {len(findings)} 处疑似重复"
        f"（重叠 ≥ {args.threshold:.0%}）："
    )
    for line in findings:
        print(f"  {line}")
    print(
        "\n→ 建议人工（须临床判断）复核：把医学语义要点保留在 scoring_points，"
        "Rule 的 must_have 收窄到确定性禁词 / 结构断言。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
