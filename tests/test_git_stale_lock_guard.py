"""test_git_stale_lock_guard.py — stale .git/index.lock 自動検知・復旧ガード (t_f01a3a9e).

一時リポジトリに lock を模擬し、scripts/git_stale_lock_guard.py の
classify / exit code / CLI 挙動をテストする。
保持プロセス（fd 保持）ケースは --selftest 側で fork 実測するため、
pytest 側は純粋に時間・存在ベースの分岐を検証する（psutil フォーク不要）。
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "git_stale_lock_guard.py"


@pytest.fixture(scope="module")
def guard_mod():
    """py スクリプト（拡張子 .py）をモジュールとしてロード。"""
    assert SCRIPT.is_file(), f"ガード不存在: {SCRIPT}"
    spec = importlib.util.spec_from_file_location("git_stale_lock_guard", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def tmp_repo(tmp_path):
    """--age=200s の閾値で用いる一時 git repo（.git/index.lock の親）。"""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    try:
        subprocess.run(
            ["git", "init", "-q", str(repo)], capture_output=True, timeout=30, check=False
        )
    except (OSError, subprocess.SubprocessError):
        pass
    return repo


def _make_stale(lock: Path, age: float = 210.0) -> None:
    lock.write_bytes(b"")
    old = time.time() - age
    os.utime(lock, (old, old))


def test_no_lock_ok(guard_mod, tmp_repo):
    rec = guard_mod.classify(tmp_repo, "index.lock", 200.0, dry_run=False)
    assert rec["status"] == guard_mod.STATUS_NO_LOCK
    assert guard_mod.exit_code_for(rec["status"]) == guard_mod.EXIT_OK


def test_stale_lock_removed(guard_mod, tmp_repo):
    lock = tmp_repo / ".git" / "index.lock"
    _make_stale(lock, age=210)
    rec = guard_mod.classify(tmp_repo, "index.lock", 200.0, dry_run=False)
    assert rec["status"] == guard_mod.STATUS_REMOVED
    assert not lock.exists(), "stale lock が未削除"
    assert guard_mod.exit_code_for(rec["status"]) == guard_mod.EXIT_OK


def test_fresh_lock_kept(guard_mod, tmp_repo):
    lock = tmp_repo / ".git" / "index.lock"
    lock.write_bytes(b"")  # 作りたて (age≈0s)
    rec = guard_mod.classify(tmp_repo, "index.lock", 200.0, dry_run=False)
    assert rec["status"] == guard_mod.STATUS_YOUNG
    assert lock.exists(), "新しい lock を削除した"
    assert guard_mod.exit_code_for(rec["status"]) == guard_mod.EXIT_HELD


def test_dry_run_detects_but_keeps(guard_mod, tmp_repo):
    lock = tmp_repo / ".git" / "index.lock"
    _make_stale(lock, age=210)
    rec = guard_mod.classify(tmp_repo, "index.lock", 200.0, dry_run=True)
    assert rec["status"] == guard_mod.STATUS_DRY_RUN
    assert lock.exists(), "dry-run なのに削除された"
    assert guard_mod.exit_code_for(rec["status"]) == guard_mod.EXIT_HELD


def test_cli_json_exit_codes(tmp_repo):
    """--dry-run --json の CLI 実測: stale 時 exit 2、no-lock 時 exit 0。"""
    lock = tmp_repo / ".git" / "index.lock"
    _make_stale(lock, age=210)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT),
         "--repo", str(tmp_repo), "--age", "200",
         "--dry-run", "--json", "--log-file", "-"],
        capture_output=True, timeout=60,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    lock.unlink()
    proc2 = subprocess.run(
        [sys.executable, str(SCRIPT),
         "--repo", str(tmp_repo), "--age", "200",
         "--json", "--log-file", "-"],
        capture_output=True, timeout=60,
    )
    assert proc2.returncode == 0, proc2.stdout + proc2.stderr
