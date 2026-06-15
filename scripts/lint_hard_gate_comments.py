"""Lint `medeval/judges/hard_gate.py` 内每张关键词/正则表上方必须有 5 行结构化注释。

要求的 5 个字段（按任意顺序均可，但缺一不可）：
    sourced:      引用来源/出处
    owners:       负责人 / 临床专家 ID（占位允许 "TBD-clinician"）
    last_reviewed:上次审核日期 (YYYY-MM-DD)
    scope:        本表覆盖的判定范围
    rationale:    为什么这样建表 / 关键决策

被守护的标识符列表见 ``_TABLES``。

退出码 0=合规；1=有表缺注释。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_TABLES = [
    "_EMERGENCY_PATTERNS",
    "_REFERRAL_PATTERNS",
    "_DOSAGE_PATTERN",
    "_FREQ_PATTERN",
    "_DIETARY_CONTEXT_WORDS",
    "_DRUG_CONTEXT_WORDS",
    "_DIAGNOSIS_PHRASES",
    "_DISCLAIMER_PATTERNS",
]

_REQUIRED_FIELDS = ("sourced:", "owners:", "last_reviewed:", "scope:", "rationale:")


def lint(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    issues: list[str] = []
    for tbl in _TABLES:
        # 找到表定义行 `_NAME = ` 或 `_NAME = re.compile(`
        pattern = re.compile(rf"^{re.escape(tbl)}\s*=")
        anchor = None
        for i, line in enumerate(lines):
            if pattern.match(line):
                anchor = i
                break
        if anchor is None:
            issues.append(f"{tbl}: 在文件中未找到该常量")
            continue
        # 向上扫描连续的 `# ...` 注释块（最多 10 行 buffer）
        block: list[str] = []
        j = anchor - 1
        while j >= 0 and lines[j].strip().startswith("#"):
            block.insert(0, lines[j].strip())
            j -= 1
        flat = "\n".join(block)
        missing = [f for f in _REQUIRED_FIELDS if f not in flat]
        if missing:
            issues.append(
                f"{tbl} (line {anchor+1}): 注释块缺少字段 {missing}"
            )
    return issues


def main() -> int:
    target = Path("medeval/judges/hard_gate.py")
    if not target.exists():
        print(f"[lint_hard_gate_comments] 找不到文件: {target}", file=sys.stderr)
        return 2
    issues = lint(target)
    if not issues:
        print(f"[lint_hard_gate_comments] ✓ {target} 内 {len(_TABLES)} 个关键词表注释完整")
        return 0
    print(
        f"[lint_hard_gate_comments] ✗ 发现 {len(issues)} 处缺失结构化注释：",
        file=sys.stderr,
    )
    for line in issues:
        print(f"  {line}", file=sys.stderr)
    print(
        "\n请在表上方添加 5 行注释 (# sourced: / # owners: / # last_reviewed: / # scope: / # rationale:)",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
