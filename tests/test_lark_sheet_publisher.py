"""Test publish_xlsx_to_lark argv shape and URL extraction."""

from __future__ import annotations

import json
from pathlib import Path

from medeval.reporter.lark_sheet_publisher import publish_xlsx_to_lark


class _FakeProc:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_returns_none_when_lark_cli_missing(tmp_path: Path, monkeypatch):
    """no lark-cli on PATH → None + warning, no exception."""
    xlsx = tmp_path / "x.xlsx"
    xlsx.write_bytes(b"PK\x03\x04stub")  # 文件存在即可
    monkeypatch.setattr("medeval.reporter.lark_sheet_publisher.shutil.which", lambda _: None)
    assert publish_xlsx_to_lark(xlsx) is None


def test_returns_none_when_xlsx_missing(tmp_path: Path):
    bogus = tmp_path / "missing.xlsx"
    assert publish_xlsx_to_lark(bogus) is None


def test_argv_shape_and_url_extraction(tmp_path: Path, monkeypatch):
    xlsx = tmp_path / "transcripts.xlsx"
    xlsx.write_bytes(b"PK\x03\x04stub")

    captured: dict = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = list(argv)
        captured["cwd"] = kwargs.get("cwd")
        return _FakeProc(
            returncode=0,
            stdout=json.dumps(
                {"data": {"file": {"url": "https://feishu/sheets/abc123"}}}
            ),
        )

    monkeypatch.setattr("medeval.reporter.lark_sheet_publisher.shutil.which", lambda _: "/x/lark-cli")
    monkeypatch.setattr("medeval.reporter.lark_sheet_publisher.subprocess.run", fake_run)

    url = publish_xlsx_to_lark(
        xlsx, parent_folder_token="folder123", title="my run"
    )
    assert url == "https://feishu/sheets/abc123"
    argv = captured["argv"]
    assert argv[:3] == ["lark-cli", "drive", "+import"]
    # lark-cli 1.0.32+ 拒绝绝对路径：必须 cd 到文件目录后传 basename
    assert "--file" in argv
    assert argv[argv.index("--file") + 1] == xlsx.name  # basename, not absolute
    assert str(xlsx) not in argv
    assert captured["cwd"] == str(xlsx.parent)
    assert "--type" in argv
    assert argv[argv.index("--type") + 1] == "sheet"
    assert "--name" in argv
    assert argv[argv.index("--name") + 1] == "my run"
    assert "--folder-token" in argv
    assert argv[argv.index("--folder-token") + 1] == "folder123"


def test_returns_none_on_nonzero_exit(tmp_path: Path, monkeypatch):
    xlsx = tmp_path / "x.xlsx"
    xlsx.write_bytes(b"PK\x03\x04stub")
    monkeypatch.setattr("medeval.reporter.lark_sheet_publisher.shutil.which", lambda _: "/x/lark-cli")
    monkeypatch.setattr(
        "medeval.reporter.lark_sheet_publisher.subprocess.run",
        lambda argv, **kw: _FakeProc(returncode=1, stderr="permission denied"),
    )
    assert publish_xlsx_to_lark(xlsx) is None


def test_returns_none_on_invalid_json(tmp_path: Path, monkeypatch):
    xlsx = tmp_path / "x.xlsx"
    xlsx.write_bytes(b"PK\x03\x04stub")
    monkeypatch.setattr("medeval.reporter.lark_sheet_publisher.shutil.which", lambda _: "/x/lark-cli")
    monkeypatch.setattr(
        "medeval.reporter.lark_sheet_publisher.subprocess.run",
        lambda argv, **kw: _FakeProc(returncode=0, stdout="not json"),
    )
    assert publish_xlsx_to_lark(xlsx) is None


def test_handles_alt_url_path(tmp_path: Path, monkeypatch):
    """URL 也可能在 data.url（兼容多种 lark-cli 输出结构）。"""
    xlsx = tmp_path / "x.xlsx"
    xlsx.write_bytes(b"PK\x03\x04stub")
    monkeypatch.setattr("medeval.reporter.lark_sheet_publisher.shutil.which", lambda _: "/x/lark-cli")
    monkeypatch.setattr(
        "medeval.reporter.lark_sheet_publisher.subprocess.run",
        lambda argv, **kw: _FakeProc(
            returncode=0,
            stdout=json.dumps({"data": {"url": "https://feishu/sheets/x"}}),
        ),
    )
    assert publish_xlsx_to_lark(xlsx) == "https://feishu/sheets/x"
