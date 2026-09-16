"""[t_f5f3bc95 / v167] protocol_violation_crash_24h の回収判定ユニットテスト。

台帳ゲート本体(tests/test_regression_gates.py::test_gate_protocol_violation_crash)は
実board DBを読むため、合成sqlite fixtureで回収判定ロジック自体の回帰を守る:
- crashが最後のrunのまま & タスク生存中 → 未回収=1（即座に赤を維持）
- crash後に同一タスクの再runあり → 回収済み=0
- タスクdone/archived終端 → 回収済み=0
恒久赤で他workerのpytest -x自己ループを阻害する構造問題(QA run524)の再発検出。
"""

from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "regression_gates_ledger_v167", REPO / "scripts" / "regression_gates_ledger.py"
)
mod = importlib.util.module_from_spec(_SPEC)  # type: ignore[arg-type]
assert _SPEC and _SPEC.loader
_SPEC.loader.exec_module(mod)

CUTOFF = 1_000.0


def _fresh_db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, status TEXT NOT NULL)")
    con.execute("CREATE TABLE task_runs (id INTEGER PRIMARY KEY, task_id TEXT, outcome TEXT, started_at REAL)")
    return con


def _add_task(con: sqlite3.Connection, tid: str, status: str) -> None:
    con.execute("INSERT INTO tasks (id, status) VALUES (?, ?)", (tid, status))


def _add_run(con: sqlite3.Connection, tid: str, outcome: str, started_at: float) -> None:
    con.execute(
        "INSERT INTO task_runs (task_id, outcome, started_at) VALUES (?, ?, ?)",
        (tid, outcome, started_at),
    )


def test_unrecovered_crash_last_run_counts() -> None:
    """crashが最後のrunでタスク生存中 → 未回収1件（ゲートは赤を維持すべき）。"""
    con = _fresh_db()
    _add_task(con, "t_a", "running")
    _add_run(con, "t_a", "completed", CUTOFF - 10)
    _add_run(con, "t_a", "crashed", CUTOFF + 10)
    out: dict[str, Any] = mod.evaluate_crash_recovery(con, CUTOFF)
    assert out["value"] == 1
    assert out["detail"].count("t_a") >= 1


def test_crash_followed_by_restart_is_recovered() -> None:
    """crash後に同一タスクの再runがある → 回収済みとして除外。"""
    con = _fresh_db()
    _add_task(con, "t_b", "running")
    _add_run(con, "t_b", "crashed", CUTOFF + 10)
    _add_run(con, "t_b", "completed", CUTOFF + 20)
    out = mod.evaluate_crash_recovery(con, CUTOFF)
    assert out["value"] == 0
    assert "recovered-by-restart-or-terminal=1" in out["detail"]


def test_crash_on_done_task_is_recovered() -> None:
    """タスクがdone/archived終端済み → 後のcrashも再発と数えない。"""
    con = _fresh_db()
    _add_task(con, "t_c", "done")
    _add_task(con, "t_d", "archived")
    _add_run(con, "t_c", "crashed", CUTOFF + 5)
    _add_run(con, "t_d", "crashed", CUTOFF + 7)
    out = mod.evaluate_crash_recovery(con, CUTOFF)
    assert out["value"] == 0
    assert "raw crashed runs=2" in out["detail"]


def test_crash_before_window_ignored() -> None:
    """cutoffより前のcrashは窓外（countしない）。窓内mixで正しく部分計上。"""
    con = _fresh_db()
    _add_task(con, "t_e", "ready")
    _add_run(con, "t_e", "crashed", CUTOFF - 100)  # 窓外
    _add_run(con, "t_e", "crashed", CUTOFF + 1)  # 窓内・最後=crashだがタスク生存・再run無
    out = mod.evaluate_crash_recovery(con, CUTOFF)
    assert out["value"] == 1
    assert "raw crashed runs=1" in out["detail"]
