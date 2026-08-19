#!/usr/bin/env python3
"""Safely apply an exported Benchmark case migration in production.

The script verifies the current exported snapshot, verifies that only the approved
case IDs differ, backs up the storage directory and exported YAML, then saves each
changed case through the same validated domain path used by the UI.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from server import benchmarks as bm_domain
from server.db import session_scope
from server.services.benchmark_catalog import export_download, get_benchmark_or_404


EXPECTED_SHA256 = {
    10: "08d012dba51e89c3aba16cb058fe0b1cad067466321cd7f2c61c81cf562f55f9",
    13: "b0ec307dae467e783765200e1d3a314afa666fededb7028dc69634db6dde86f7",
}

EXPECTED_CHANGED_IDS = {
    10: {
        "case_7", "case_10", "case_16", "case_23", "case_25", "case_26",
        "case_27", "case_29", "case_31", "case_50", "case_52", "case_53",
        "case_61", "case_63", "case_65", "case_73", "case_76", "case_78",
        "case_81", "case_92", "case_93",
    },
    13: {
        "case_3", "case_14", "case_30", "case_35", "case_41", "case_43",
        "case_47", "case_51", "case_52", "case_59", "case_60", "case_61",
    },
}


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _map_cases(data: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item["sample_id"]): item for item in data}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark-id", type=int, choices=(10, 13), required=True)
    parser.add_argument("--migrated", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    migrated_data = yaml.safe_load(args.migrated.read_text(encoding="utf-8"))
    if not isinstance(migrated_data, list):
        raise SystemExit("迁移文件顶层必须是 Case 列表")
    migrated = _map_cases(migrated_data)

    with session_scope() as session:
        benchmark = get_benchmark_or_404(session, args.benchmark_id)
        _, current_text = export_download(args.benchmark_id, session)
        current_hash = _sha256_text(current_text)
        expected_hash = EXPECTED_SHA256[args.benchmark_id]
        if current_hash != expected_hash:
            raise SystemExit(
                f"Benchmark {args.benchmark_id} 生产快照已变化，停止更新："
                f"expected={expected_hash}, actual={current_hash}"
            )
        current_data = yaml.safe_load(current_text)
        current = _map_cases(current_data)
        if current.keys() != migrated.keys():
            raise SystemExit("迁移前后 Case ID 集合不一致")
        changed = {sample_id for sample_id in current if current[sample_id] != migrated[sample_id]}
        if changed != EXPECTED_CHANGED_IDS[args.benchmark_id]:
            raise SystemExit(
                f"变更 Case 集合不符合审批范围：expected={sorted(EXPECTED_CHANGED_IDS[args.benchmark_id])}, "
                f"actual={sorted(changed)}"
            )

        print(
            f"DRY-RUN benchmark={args.benchmark_id} name={benchmark.name!r} "
            f"cases={len(current)} changed={len(changed)} storage={benchmark.storage_path}"
        )
        if not args.apply:
            return

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_root = Path("/data/benchmark_migration_backups") / stamp / f"benchmark_{args.benchmark_id}"
        backup_root.mkdir(parents=True, exist_ok=False)
        (backup_root / "export_before.yaml").write_text(current_text, encoding="utf-8")
        storage = Path(benchmark.storage_path)
        if not storage.is_dir():
            raise SystemExit(f"Benchmark 存储目录不存在：{storage}")
        shutil.copytree(storage, backup_root / "storage")

        try:
            for sample_id in sorted(changed, key=lambda value: int(value.split("_")[1])):
                text = yaml.safe_dump(
                    [migrated[sample_id]], allow_unicode=True, sort_keys=False, width=1000
                )
                bm_domain.save_case_yaml(benchmark, sample_id, text)
            benchmark.mark_updated()

            _, after_text = export_download(args.benchmark_id, session)
            after = _map_cases(yaml.safe_load(after_text))
            if after != migrated:
                raise RuntimeError("生产回读结果与迁移文件不一致")
            (backup_root / "export_after.yaml").write_text(after_text, encoding="utf-8")
        except Exception:
            # Case 内容落在文件系统，不受数据库事务回滚保护；失败时立即恢复完整目录。
            shutil.rmtree(storage)
            shutil.copytree(backup_root / "storage", storage)
            raise
        print(
            f"APPLIED benchmark={args.benchmark_id} changed={len(changed)} "
            f"backup={backup_root} sha256_after={_sha256_text(after_text)}"
        )


if __name__ == "__main__":
    main()
