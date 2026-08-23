"""lock.py — acquire_pid_lock の状態検出テスト。

シナリオ:
  1. ロックなし → 取得成功（PID+開始時刻が記録される）
  2. 既存プロセス生存・正常 → ブロック (None)
  3. 既存PIDが死んでいる → ロック再利用（引き継ぎ）
  4. 既存プロセス生存・stale超過・自ワーカー → killして引き継ぎ
  5. 既存プロセス生存・stale超過・別プログラム → ブロック（PID再利用対策）
"""

from __future__ import annotations

import time

import psutil
import pytest

import kensho.core.lock as lock_mod
from kensho.core.lock import acquire_pid_lock


@pytest.fixture(autouse=True)
def _use_tmp_lock_base(tmp_path, monkeypatch):
    """各テストで LOCK_BASE を tmp_path に差し替え、実data/locksを汚さない。"""
    monkeypatch.setattr(lock_mod, "LOCK_BASE", tmp_path)
    yield tmp_path


# ── ヘルパー ──


def _write_old_lock(lock_path, pid: int, age_seconds: float):
    """staleロックファイルを直接書く（旧形式3行or2行）。"""
    start_ts = time.time() - age_seconds
    lock_path.write_text(f"{pid}\n{start_ts}\n", encoding="utf-8")


class _FakeProc:
    """psutil.Process のフェイク。cmdline しか使わないので十分。"""

    def __init__(self, cmdline):
        self._cmdline = cmdline

    def cmdline(self):
        return self._cmdline

    def children(self, recursive=True):
        return []

    def kill(self):
        pass


@pytest.fixture
def make_fake_proc(monkeypatch):
    """psutil.Process / psutil.pid_exists を差し替えるファクトリを返す。"""

    def _make(alive: bool, cmdline: list[str] | None = None):
        monkeypatch.setattr(psutil, "pid_exists", lambda pid: alive)

        if cmdline is not None:
            fake = _FakeProc(cmdline)
            monkeypatch.setattr(psutil.Process, "__new__", lambda cls: fake)
        else:
            # alive=True で cmdline 未指定 → access denied 相当
            def _denied(*a, **k):
                raise psutil.AccessDenied

            monkeypatch.setattr(psutil.Process, "cmdline", _denied)

    return _make


# ── テスト ──


def test_no_lock_success(tmp_path, monkeypatch):
    """ロックなし → 取得成功、PID+開始時刻が書かれる。"""
    got = acquire_pid_lock("orchestrator", max_stale_seconds=3600)

    assert got is not None
    assert got.exists()
    lines = got.read_text(encoding="utf-8").strip().splitlines()
    assert int(lines[0]) == __import__("os").getpid()
    assert len(lines) >= 2  # 開始時刻が書かれている


def test_alive_normal_blocks(tmp_path, monkeypatch, make_fake_proc):
    """既存プロセス生存・正常 → ブロック (None)。"""
    make_fake_proc(alive=True, cmdline=["python", "kensho/orchestrator.py"])
    _write_old_lock(tmp_path / "orchestrator.pid", pid=9999, age_seconds=60)

    got = acquire_pid_lock("orchestrator", max_stale_seconds=3600)
    assert got is None


def test_dead_pid_reuses_lock(tmp_path, monkeypatch, make_fake_proc):
    """既存PIDが死んでいる → ロック再利用で取得成功。"""
    make_fake_proc(alive=False)
    _write_old_lock(tmp_path / "orchestrator.pid", pid=9999, age_seconds=99999)

    got = acquire_pid_lock("orchestrator", max_stale_seconds=3600)
    assert got is not None
    assert got.exists()


def test_stale_our_worker_killed(tmp_path, monkeypatch, make_fake_proc):
    """生存 + stale超過 + 自ワーカー → killして引き継ぐ。"""
    killed = []

    class _FakeProcWithKill(_FakeProc):
        def kill(self):
            killed.append(True)

    fake = _FakeProcWithKill(["python", "kensho/orchestrator.py"])
    monkeypatch.setattr(psutil, "pid_exists", lambda pid: True)
    monkeypatch.setattr(psutil, "Process", lambda pid: fake)

    _write_old_lock(tmp_path / "orchestrator.pid", pid=9999, age_seconds=99999)

    got = acquire_pid_lock("orchestrator", max_stale_seconds=3600)
    assert got is not None
    assert killed, "旧プロセスがkillされていない"


def test_stale_other_program_blocks(tmp_path, monkeypatch, make_fake_proc):
    """生存 + stale超過 + 別プログラム(再利用) → ブロック。"""
    fake = _FakeProc(["python", "/home/x/unrelated.py"])
    monkeypatch.setattr(psutil, "pid_exists", lambda pid: True)
    monkeypatch.setattr(psutil, "Process", lambda pid: fake)

    _write_old_lock(tmp_path / "orchestrator.pid", pid=9999, age_seconds=99999)

    got = acquire_pid_lock("orchestrator", max_stale_seconds=3600)
    assert got is None


def test_old_format_no_start_ts_blocks(tmp_path, monkeypatch, make_fake_proc):
    """旧形式(PIDのみ・開始時刻なし) + 生存 → 保守的にブロック。"""
    make_fake_proc(alive=True, cmdline=["python", "kensho/orchestrator.py"])
    (tmp_path / "orchestrator.pid").write_text("9999", encoding="utf-8")

    got = acquire_pid_lock("orchestrator", max_stale_seconds=3600)
    assert got is None
