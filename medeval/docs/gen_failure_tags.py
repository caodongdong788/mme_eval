"""把 FailureTag 词表渲染为 Markdown，用于 README 的 AUTO-GENERATED 段。

用法：
    python -m medeval.docs.gen_failure_tags         # 打印到 stdout
    python -m medeval.docs.gen_failure_tags --check # 比对 README 是否一致 (退出码非 0 即不同步)
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

from medeval.models import FailureTag, _TAG_META  # noqa: PLC2701

_DIM_TITLE: dict[str, str] = {
    "red_flag": "红旗症状 / 分诊",
    "prescription": "处方边界",
    "communication": "问诊 / 沟通 / 鉴别",
    "system": "系统 / 框架",
}

_MARKER_START = "<!-- AUTO-GENERATED:failure-tags-start -->"
_MARKER_END = "<!-- AUTO-GENERATED:failure-tags-end -->"


def render() -> str:
    by_dim: dict[str, list[FailureTag]] = defaultdict(list)
    for tag in FailureTag:
        by_dim[tag.dimension].append(tag)

    lines: list[str] = [
        _MARKER_START,
        "",
        "> 本段由 `python -m medeval.docs.gen_failure_tags` 自动生成，请勿手动编辑。",
        "",
    ]
    for dim, title in _DIM_TITLE.items():
        tags = by_dim.get(dim, [])
        if not tags:
            continue
        lines += [
            f"### {title} (`{dim}`)",
            "",
            "| 短标签 | 英文 enum | 详细说明 |",
            "|-|-|-|",
        ]
        for t in tags:
            lines.append(f"| {t.label_zh} | `{t.value}` | {t.description} |")
        lines.append("")
    lines.append(_MARKER_END)
    return "\n".join(lines).rstrip() + "\n"


def patch_readme(readme_path: Path) -> tuple[str, str]:
    """返回 (旧片段, 新片段)。"""
    text = readme_path.read_text(encoding="utf-8")
    new_block = render().rstrip()

    pattern = re.compile(
        rf"{re.escape(_MARKER_START)}.*?{re.escape(_MARKER_END)}", re.DOTALL
    )
    if pattern.search(text):
        old_block = pattern.search(text).group(0)  # type: ignore[union-attr]
        updated = pattern.sub(new_block, text)
    else:
        # 首次注入：在"## 失败归因标签"段下方覆盖
        section = re.compile(r"^## 失败归因标签.*?^---", re.DOTALL | re.MULTILINE)
        if not section.search(text):
            raise SystemExit("README 中找不到'## 失败归因标签'段，无法注入标记")
        old_block = section.search(text).group(0)  # type: ignore[union-attr]
        replacement = f"## 失败归因标签\n\n{new_block}\n\n---"
        updated = section.sub(replacement, text)
    readme_path.write_text(updated, encoding="utf-8")
    return old_block, new_block


def check(readme_path: Path) -> int:
    text = readme_path.read_text(encoding="utf-8")
    new_block = render().rstrip()
    pattern = re.compile(
        rf"{re.escape(_MARKER_START)}.*?{re.escape(_MARKER_END)}", re.DOTALL
    )
    m = pattern.search(text)
    if not m:
        print("[gen_failure_tags] README 缺少 AUTO-GENERATED 标记块", file=sys.stderr)
        return 1
    if m.group(0).strip() != new_block.strip():
        print(
            "[gen_failure_tags] ✗ README 与 FailureTag 词表不一致。"
            " 请运行: python -m medeval.docs.gen_failure_tags --write",
            file=sys.stderr,
        )
        return 1
    print("[gen_failure_tags] ✓ README 与 FailureTag 词表一致")
    return 0


def main() -> int:
    readme = Path("README.md")
    if "--check" in sys.argv:
        return check(readme)
    if "--write" in sys.argv:
        patch_readme(readme)
        print(f"[gen_failure_tags] ✓ 已更新 {readme}")
        return 0
    print(render())
    return 0


if __name__ == "__main__":
    sys.exit(main())
