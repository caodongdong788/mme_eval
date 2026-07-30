#!/usr/bin/env python3
"""Print the MME production runtime dependency set from pyproject.toml."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path


RUNTIME_EXTRAS = ("server", "llm-openai", "langfuse", "postgres")


def main() -> None:
    document = tomllib.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    project = document["project"]
    dependencies = list(project.get("dependencies", []))
    optional = project.get("optional-dependencies", {})
    for extra in RUNTIME_EXTRAS:
        dependencies.extend(optional[extra])

    # 保持 pyproject 中的顺序，同时去重，便于 Docker layer 稳定命中缓存。
    print("\n".join(dict.fromkeys(dependencies)))


if __name__ == "__main__":
    main()
