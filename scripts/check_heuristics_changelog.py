"""CI 检查：当 HardGate fingerprint 变化时，必须同步更新 CHANGELOG。

逻辑：
  1. 计算当前 HardGateJudge fingerprint。
  2. 在 `docs/heuristics-changelog.md` 中搜索该 fingerprint 字符串。
  3. 若找不到则 fail：开发者必须新增一段 CHANGELOG 记录。

设计取舍：
  - 不依赖 git diff（CI 上获取 base 分支文件不总是可靠）。
  - 改为"fingerprint 必须出现在 CHANGELOG"，对开发者更直观，
    任何时候本地 / CI 跑结果都一致。

退出码 0=合规；1=fingerprint 未登记到 CHANGELOG。
"""

from __future__ import annotations

import sys
from pathlib import Path

from medeval.judges.hard_gate import HardGateJudge

CHANGELOG = Path("docs/heuristics-changelog.md")


def main() -> int:
    if not CHANGELOG.exists():
        print(f"[check_heuristics_changelog] 找不到 {CHANGELOG}", file=sys.stderr)
        return 2

    fp = HardGateJudge().fingerprint()
    text = CHANGELOG.read_text(encoding="utf-8")
    if fp in text:
        print(f"[check_heuristics_changelog] ✓ fingerprint {fp} 已登记在 CHANGELOG")
        return 0

    print(
        f"[check_heuristics_changelog] ✗ 当前 HardGate fingerprint = {fp} "
        f"但 {CHANGELOG} 中未登记。",
        file=sys.stderr,
    )
    print(
        "请在 docs/heuristics-changelog.md 顶部新增一段记录（含 Fingerprint / "
        "Author / Reviewers / Scope / Changes / Golden Tests Impact）。",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
