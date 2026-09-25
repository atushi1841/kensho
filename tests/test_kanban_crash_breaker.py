"""Tests for scripts/kanban_crash_breaker.py — 盤面側クラッシュループ遮断器（t_5ecf88bf）

背景（実測 2026-09-25）:
  * hermes core は clean-exit protocol violation を意図的に失敗予算外に置くため
    `consecutive_failures` が加算されず、failure_limit ベースの breaker は発火しない。
  * 24h 窓で crashed=250 / 1 枚最大 64 回 crash / 浪費時間率 43.4%。盤面側で park するしかない。
  * 旧 scripts/kanban_crash_stats.sh は `sqlite3` CLI が無い環境で無音失敗し（末尾 `rm` が
    exit 0 を返すため cron からは正常に見えた）、参照 DB も存在しないパスだった。

本テストは (1) 統計の正しさ (2) park 対象の選定（live claim 保護を含む）(3) CLI 呼出の
実挙動（fake hermes バイナリで schedule 引数を捕捉）(4) 安全弁（dry-run / kill switch /
DB 不在 / 冪等性）(5) 旧バグの静的再発防止 を検証する。

ネットワーク不使用・共有盤面 DB へは読み取りもしない（すべて tmp_path の合成 DB で完結）。
"""

from __future__ import annotations

import json
import os
import sqlite3
import stat
import sys
import time
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import kanban_crash_breaker as mod  # noqa: E402

REPO_ROOT = Path(__file__).parent.parent
STATS_SH = REPO_ROOT / "scripts" / "kanban_crash_stats.sh"
BREAKER_SH = REPO_ROOT / "scripts" / "kanban_crash_circuit_breaker.sh"

NOW = 1_800_000_000


def _make_db(path: Path, tasks: list[tuple[str, str, str, int | None]], runs: list[tuple[str, str, str, int, int | None]]) -> Path:
    """合成盤面 DB を作る。

    tasks: (id, assignee, status, claim_expires)
    runs:  (task_id, profile, outcome, started_at, ended_at)
    """
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE tasks (id TEXT PRIMARY KEY, assignee TEXT, status TEXT, claim_expires INTEGER)"
    )
    con.execute(
        "CREATE TABLE task_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, profile TEXT,"
        " outcome TEXT, started_at INTEGER, ended_at INTEGER)"
    )
    con.executemany("INSERT INTO tasks VALUES (?,?,?,?)", tasks)
    con.executemany("INSERT INTO task_runs (task_id, profile, outcome, started_at, ended_at) VALUES (?,?,?,?,?)", runs)
    con.commit()
    con.close()
    return path


def _fake_hermes(tmp_path: Path) -> tuple[Path, Path]:
    """schedule 呼出を記録する fake hermes バイナリを作る。"""
    bin_path = tmp_path / "fake-hermes"
    call_log = tmp_path / "hermes-calls.log"
    bin_path.write_text(f'#!/bin/bash\nprintf "%s\\n" "$*" >> "{call_log}"\nexit 0\n', encoding="utf-8")
    bin_path.chmod(bin_path.stat().st_mode | stat.S_IEXEC)
    return bin_path, call_log


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """合成盤面・fake hermes・ログ・安全弁パスを環境変数へ流し込む。"""
    db = _make_db(
        tmp_path / "kanban.db",
        tasks=[("t_ready_crash", "kensho-worker", "ready", None)],
        runs=[],
    )
    bin_path, call_log = _fake_hermes(tmp_path)
    log_path = tmp_path / "logs" / "crash_breaker.log"
    monkeypatch.setenv("KANBAN_DB", str(db))
    monkeypatch.setenv("KANBAN_BOARD", "testboard")
    monkeypatch.setenv("HERMES_BIN", str(bin_path))
    monkeypatch.setenv("CRASH_BREAKER_LOG", str(log_path))
    monkeypatch.setenv("CRASH_BREAKER_DISABLE_FILE", str(tmp_path / "nope.disabled"))
    monkeypatch.setenv("CRASH_BREAKER_THRESHOLD", "3")
    monkeypatch.delenv("CRASH_BREAKER_DRY_RUN", raising=False)
    return {"db": db, "bin": bin_path, "calls": call_log, "log": log_path, "tmp": tmp_path}


# ── 1. stats の正しさ ────────────────────────────────────────────────────────


def test_stats_counts_crashes_waste_and_ready_zero_run(env: dict[str, Any]) -> None:
    """24h 窓の crash 件数・最大値・浪費率・未着手 ready を数える。"""
    _ = env
    db = _make_db(
        env["tmp"] / "stats.db",
        tasks=[
            ("t_a", "kensho-worker", "done", None),
            ("t_b", "kensho-worker", "ready", None),
            ("t_c", "kensho-qa", "running", NOW + 600),
        ],
        runs=[
            # t_a: crash 2 回（各 600s 浪費）+ 完走 1 回 600s
            ("t_a", "kensho-worker", "crashed", NOW - 3600, NOW - 3000),
            ("t_a", "kensho-worker", "crashed", NOW - 3000, NOW - 2400),
            ("t_a", "kensho-worker", "completed", NOW - 2400, NOW - 1800),
            # t_c: crash 3 回（各 600s）
            ("t_c", "kensho-qa", "crashed", NOW - 1800, NOW - 1200),
            ("t_c", "kensho-qa", "crashed", NOW - 1200, NOW - 600),
            ("t_c", "kensho-qa", "crashed", NOW - 600, NOW),
        ],
        # 窓外（25h 前）は無視される
    )
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO task_runs (task_id, profile, outcome, started_at, ended_at) VALUES (?,?,?,?,?)",
        ("t_a", "kensho-worker", "crashed", NOW - 25 * 3600, NOW - 25 * 3600 + 100),
    )
    con.commit()
    con.close()

    stats = mod.collect_stats(str(db), 24, now=NOW)

    assert stats["window_h"] == 24
    assert stats["crashed_total"] == 5, "窓外の crash を混ぜていない"
    assert stats["max_crashes_per_task"] == 3
    # 浪費 = crash 5 回 × 600s = 3000 / 総時間 3600 = 83.3%
    assert stats["waste_ratio_pct"] == 83.3
    assert stats["ready_zero_run"] == 1, "run が 1 件も無い ready は t_b のみ"
    assert [t["id"] for t in stats["top_tasks"]] == ["t_c", "t_a"]
    assert stats["top_tasks"][0]["claim_expired"] is False, "t_c は claim 有効（NOW+600）"
    assert stats["waste_by_profile_pct"]["kensho-qa"] == 100.0


def test_stats_is_read_only(env: dict[str, Any]) -> None:
    """集計は盤面 DB を書き換えない（read-only URI）。"""
    _ = env
    db = _make_db(env["tmp"] / "ro.db", [("t_a", "kensho-worker", "ready", None)], [("t_a", "x", "crashed", NOW - 10, NOW)])
    before = db.read_bytes()
    mod.collect_stats(str(db), 24, now=NOW)
    assert db.read_bytes() == before


# ── 2. park 対象の選定 ───────────────────────────────────────────────────────


def _stats_with(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"top_tasks": rows, "crashed_total": len(rows), "max_crashes_per_task": 9, "waste_ratio_pct": 0.0}


def test_select_candidates_parks_ready_over_threshold() -> None:
    parkable, skipped = mod.select_candidates(
        _stats_with([{"id": "t_x", "crashes": 5, "status": "ready", "claim_expired": True}]), 3
    )
    assert [r["id"] for r in parkable] == ["t_x"]
    assert skipped == []


def test_select_candidates_protects_live_running_claim() -> None:
    """稼働中 worker のカードは殺さない（実測 9/25: running 2 枚は live claim だった）。"""
    parkable, skipped = mod.select_candidates(
        _stats_with([{"id": "t_live", "crashes": 18, "status": "running", "claim_expired": False}]), 3
    )
    assert parkable == []
    assert [r["id"] for r in skipped] == ["t_live"]


def test_select_candidates_parks_running_with_expired_claim() -> None:
    parkable, skipped = mod.select_candidates(
        _stats_with([{"id": "t_stale", "crashes": 4, "status": "running", "claim_expired": True}]), 3
    )
    assert [r["id"] for r in parkable] == ["t_stale"]
    assert skipped == []


def test_select_candidates_ignores_done_and_below_threshold() -> None:
    parkable, skipped = mod.select_candidates(
        _stats_with(
            [
                {"id": "t_done", "crashes": 64, "status": "done", "claim_expired": True},
                {"id": "t_low", "crashes": 2, "status": "ready", "claim_expired": True},
            ]
        ),
        3,
    )
    assert parkable == [] and skipped == []


# ── 3. run の実挙動（fake hermes で CLI 引数を捕捉） ─────────────────────────


def test_run_parks_ready_card_via_cli(env: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    """閾値超過の ready カードが hermes kanban schedule で park される。"""
    real_now = int(time.time())
    _make_db(
        env["db"],
        tasks=[("t_ready_crash", "kensho-worker", "ready", None)],
        runs=[("t_ready_crash", "kensho-worker", "crashed", real_now - 600 - i, real_now - 300 - i) for i in range(4)],
    )
    rc = mod.cmd_run()
    out = capsys.readouterr().out.strip()

    assert rc == 0
    assert env["calls"].exists(), "hermes CLI が呼ばれていない"
    calls = env["calls"].read_text(encoding="utf-8").strip().splitlines()
    assert len(calls) == 1
    assert calls[0].startswith("kanban --board testboard schedule t_ready_crash")
    assert "crash-loop breaker: 4 crashes/24h" in calls[0]
    summary = json.loads(out)
    assert summary["parked"] == 1 and summary["parked_ids"] == ["t_ready_crash"]
    assert summary["candidates"] == 1 and summary["threshold"] == 3
    assert env["log"].exists(), "実行ログが残っていない"


def test_run_dry_run_does_not_call_cli(env: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    real_now = int(time.time())
    _make_db(
        env["db"],
        tasks=[("t_ready_crash", "kensho-worker", "ready", None)],
        runs=[("t_ready_crash", "kensho-worker", "crashed", real_now - 600 - i, real_now - 300 - i) for i in range(5)],
    )
    monkeypatch.setenv("CRASH_BREAKER_DRY_RUN", "1")
    assert mod.cmd_run() == 0
    assert not env["calls"].exists(), "dry-run で CLI を呼んではならない"


def test_run_kill_switch_disables_breaker(env: dict[str, Any], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    disable = env["tmp"] / "disabled"
    disable.write_text("", encoding="utf-8")
    monkeypatch.setenv("CRASH_BREAKER_DISABLE_FILE", str(disable))
    assert mod.cmd_run() == 0
    assert json.loads(capsys.readouterr().out)["reason"] == "disabled"
    assert not env["calls"].exists()


def test_run_missing_db_is_silent_success(env: dict[str, Any], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("KANBAN_DB", str(env["tmp"] / "absent.db"))
    assert mod.cmd_run() == 0
    assert json.loads(capsys.readouterr().out)["reason"] == "db_not_found"


def test_run_is_silent_and_idempotent_when_nothing_to_park(env: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    """park 済み（status=scheduled）や閾値未満では何も出力しない = no_agent cron の無音平常運転。"""
    _ = env
    assert mod.cmd_run() == 0
    assert capsys.readouterr().out == ""
    assert not env["calls"].exists()


def test_run_reports_cli_failure(env: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    """CLI が失敗したら failed として要約に載せる（無音で握り潰さない）。"""
    real_now = int(time.time())
    _make_db(
        env["db"],
        tasks=[("t_ready_crash", "kensho-worker", "ready", None)],
        runs=[("t_ready_crash", "kensho-worker", "crashed", real_now - 600 - i, real_now - 300 - i) for i in range(4)],
    )
    env["bin"].write_text('#!/bin/bash\necho "boom" >&2\nexit 3\n', encoding="utf-8")
    env["bin"].chmod(env["bin"].stat().st_mode | stat.S_IEXEC)
    assert mod.cmd_run() == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["parked"] == 0
    assert summary["failed"][0]["id"] == "t_ready_crash"
    assert summary["failed"][0]["rc"] == "3"


# ── 4. 旧バグの静的再発防止 ──────────────────────────────────────────────────


def test_sh_wrappers_avoid_sqlite3_cli_and_point_to_module() -> None:
    """旧版の無音失敗（sqlite3 CLI 不在・存在しない DB パス）を二度と混入させない。"""
    import re

    for sh in (STATS_SH, BREAKER_SH):
        text = sh.read_text(encoding="utf-8")
        assert sh.exists()
        assert "kanban_crash_breaker.py" in text
        assert not re.search(r"(?m)^\s*sqlite3\s", text), f"{sh.name} は sqlite3 CLI を実行してはならない"
        assert "/hermes/kanban/kanban.db" not in text, f"{sh.name} は存在しない DB パスを参照してはならない"
        assert os.access(sh, os.X_OK), f"{sh.name} に実行ビットが無い"


def test_module_has_no_third_party_imports() -> None:
    """cron 最小 PATH でも動くよう標準ライブラリのみで完結していること。"""
    text = (REPO_ROOT / "scripts" / "kanban_crash_breaker.py").read_text(encoding="utf-8")
    for banned in ("import requests", "import yaml", "import psutil", "import loguru"):
        assert banned not in text
