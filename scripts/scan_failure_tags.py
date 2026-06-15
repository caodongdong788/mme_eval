"""扫描所有 cases YAML，列出 `failure_tags_candidates` 中不在 FailureTag 词表内的取值。

用法：
    python scripts/scan_failure_tags.py [cases_dir]

输出每行：
    <file>:<line>  sample_id=<id>  bad_tag=<tag>  推荐映射=<migration>

退出码：
    0 ── 全部合法
    1 ── 存在非法 candidate

迁移映射表（见 consolidate-failure-tags/design.md 决策 4）：
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

from medeval.models import FailureTag

VALID = {t.value for t in FailureTag}

# 迁移映射：旧字符串 -> (推荐 FailureTag, 备注/动作)
MIGRATION: dict[str, tuple[str | None, str]] = {
    "prompt_injection_success": (
        "constraint_violation",
        "语义保留到 case tags 字段(如 adversarial / prompt_injection)",
    ),
    "safety_violation": (
        None,
        "拆为 improper_prescription 或 missed_red_flag，按用例语境选",
    ),
    "privacy_violation": (
        "constraint_violation",
        "P2 隐私维度 Judge 上线后再细分",
    ),
    # 预留成员已是 Enum 成员，不需要迁移，但用例作者可能没意识到它们"暂不会被 emit"
}


def scan(cases_dir: Path) -> list[str]:
    issues: list[str] = []
    for yml in sorted(cases_dir.rglob("*.yaml")):
        text = yml.read_text(encoding="utf-8")
        # 简单解析：找到每个 sample_id 块对应的行号
        data = yaml.safe_load(text) or []
        items = data if isinstance(data, list) else [data]
        for item in items:
            sid = item.get("sample_id", "?")
            candidates = item.get("failure_tags_candidates") or []
            for tag in candidates:
                if tag not in VALID:
                    mapped, note = MIGRATION.get(tag, (None, "未知标签，需人工决定"))
                    target = f"→ {mapped}" if mapped else "→ 无直接映射"
                    issues.append(
                        f"{yml.relative_to(cases_dir.parent)}  sample_id={sid}"
                        f"  bad_tag={tag}  {target}  ({note})"
                    )
    return issues


def main() -> int:
    cases = Path(sys.argv[1] if len(sys.argv) > 1 else "cases")
    if not cases.exists():
        print(f"[scan_failure_tags] 目录不存在: {cases}", file=sys.stderr)
        return 2
    issues = scan(cases)
    if not issues:
        print(f"[scan_failure_tags] ✓ {cases} 下所有 failure_tags_candidates 合法")
        return 0
    print(f"[scan_failure_tags] ✗ 发现 {len(issues)} 处非法 candidate：")
    for line in issues:
        print(f"  {line}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
