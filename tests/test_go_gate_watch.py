"""go_gate_watch.sh 検出ロジックテスト (critic v155 / t_a085ab68).

根拠事故: t_ed8baffa 2026-09-16 01:11 run490 — 本文「ユーザーGO必須」+
created(blocked)→promoted→claimed が同一run内10秒（task_events 14257-14260）。
作業者自身がGO承認ゲートを素通りしたため、read-only監視（通知のみ）を導入。

不変条件:
  1. 事故パターン（blocked起票+GOマーカー+人間GO前にclaimed）を必ず検出
  2. GOマーカーなし通常カード / ready起票 / 人間GO後claimed は誤検知0
  3. state dedup により同一 task:run の再通知が発生しない
  4. --selftest が exit 0
"""

import json
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "go_gate_watch.sh"

T0 = int(datetime(2026, 9, 16, 1, 11, 20).timestamp())


def _build_db(path: Path) -> None:
    """tmp kanban.db fixture: 事故1件 + 誤検知候補3件."""
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        create table tasks (
            id TEXT PRIMARY KEY, title TEXT NOT NULL DEFAULT '', body TEXT,
            assignee TEXT, status TEXT NOT NULL DEFAULT 'todo'
        );
        create table task_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL, run_id INTEGER, kind TEXT NOT NULL,
            payload TEXT, created_at INTEGER NOT NULL
        );
        """
    )

    def task(tid, body, status="blocked"):
        conn.execute(
            "insert into tasks(id,title,body,status) values(?,?,?,?)",
            (tid, "fixture " + tid, body, status),
        )

    def ev(tid, kind, at, run_id=None, payload=None):
        conn.execute(
            "insert into task_events(task_id,run_id,kind,payload,created_at) values(?,?,?,?,?)",
            (tid, run_id, kind, payload, T0 + at),
        )

    # 事故再現（t_ed8baffa 実測そのまま: created(blocked)→promoted→claimed 10秒）
    task("t_incident01", "本番投入前にユーザーGO必須。Telegram経由のみ承認。")
    ev("t_incident01", "created", 0, payload=json.dumps({"status": "blocked"}))
    ev("t_incident01", "promoted", 10)
    ev("t_incident01", "claimed", 10, run_id=490)
    ev("t_incident01", "spawned", 10, run_id=490)
    # 通常カード（マーカーなし）→ 検出してはいけない
    task("t_clean01", "収集ログの定期ローテート", "done")
    ev("t_clean01", "created", 0, payload=json.dumps({"status": "todo"}))
    ev("t_clean01", "claimed", 5, run_id=491)
    # ready起票+GOマーカー（t_cafe0cdd/t_b9a55d7a形状: GO済みで通常起票）→ 検出不可
    task("t_ready01", "research提案A・ユーザーGO承認済みで起票", "done")
    ev("t_ready01", "created", 0, payload=json.dumps({"status": "ready"}))
    ev("t_ready01", "claimed", 3, run_id=492)
    # 人間GO (unblocked) 後の claimed = 正常フロー → 検出不可
    task("t_go01", "ユーザーGO必須の適用カード", "running")
    ev("t_go01", "created", 0, payload=json.dumps({"status": "blocked"}))
    ev("t_go01", "unblocked", 3600)
    ev("t_go01", "promoted", 3610)
    ev("t_go01", "claimed", 3620, run_id=493)
    conn.commit()
    conn.close()


def _run_watch(tmp_path: Path, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    import os

    env = dict(os.environ)
    env.update({
        "GO_GATE_DB": str(tmp_path / "board.db"),
        "GO_GATE_STATE": str(tmp_path / "state.json"),
        "GO_GATE_LOG": str(tmp_path / "logs" / "go_gate_watch.log"),
        "GO_GATE_NOTIFY_SH": str(tmp_path / "no_such_notify.sh"),
    })
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(SCRIPT), "--no-notify"],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )


def _prepare(tmp_path: Path) -> None:
    _build_db(tmp_path / "board.db")


def test_selftest_exit_zero() -> None:
    """成否指標②: bash go_gate_watch.sh --selftest → exit_code=0."""
    proc = subprocess.run(
        ["bash", str(SCRIPT), "--selftest"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, f"selftest failed: {proc.stdout}\n{proc.stderr}"
    assert "SELFTEST OK" in proc.stdout


def test_detects_incident_pattern(tmp_path: Path) -> None:
    """事故パターン（t_ed8baffa相当）を必ず1件検出し、ログへ1行警告を残す."""
    _prepare(tmp_path)
    proc = _run_watch(tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "task=t_incident01" in proc.stdout
    assert "GO-GATE WARNING" in proc.stdout
    log = tmp_path / "logs" / "go_gate_watch.log"
    assert log.exists()
    lines = [ln for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1 and "t_incident01" in lines[0]


def test_zero_false_positives(tmp_path: Path) -> None:
    """GO済み通常カード3種（マーカーなし/ready起票/人間GO後）は誤検知0件."""
    _prepare(tmp_path)
    proc = _run_watch(tmp_path)
    for neg in ("t_clean01", "t_ready01", "t_go01"):
        assert neg not in proc.stdout


def test_dedup_state_no_renotify(tmp_path: Path) -> None:
    """stateファイルにより同一 task:run の二重通知が発生しない."""
    _prepare(tmp_path)
    first = _run_watch(tmp_path)
    assert "t_incident01" in first.stdout
    second = _run_watch(tmp_path)
    assert second.returncode == 0
    assert second.stdout.strip() == ""
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert "t_incident01:490" in state["alerted"]


def test_missing_db_is_silent_ok(tmp_path: Path) -> None:
    """DB不在（ボード未作成環境）でも異常終了しない（exit 0・無出力）."""
    env = {"GO_GATE_DB": str(tmp_path / "nonexistent.db")}
    proc = _run_watch(tmp_path, env)
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""
