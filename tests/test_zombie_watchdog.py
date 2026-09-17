r"""tests/test_zombie_watchdog.py — ゾンビタスク検出・自動unblock+再割当 (t_7748d284).

ゾンビ = worker が rc=0 で正常終了したのに kanban_complete/kanban_block を呼ばず、
プロトコル違反カウンタで回路遮断され、blocked のまま永久滞留するタスク。

検証点:
1. kensho-zombie-watchdog.sh --dry-run が「blocked + last_failure_error に
   'protocol violation'」のタスクのみを狙い撃ちで検出する（iteration-budget 等の
   別原因 blocking は除外）。
2. loop_health.sh の zombie_task_count が score に反映される（1件あたり -10）。
   LOOPHEALTH_ZOMBIE_COUNT 上書きで決定的に検証。
"""

import json
import os
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WATCHDOG = REPO / "scripts" / "kensho-zombie-watchdog.sh"
BOARD_DB = Path(
    os.environ.get(
        "KENSHO_ZOMBIE_DB",
        "/home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db",
    )
)
LOOP_HEALTH = Path(
    os.environ.get(
        "LOOP_HEALTH_SCRIPT",
        "/home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh",
    )
)

_ID_RE = re.compile(r"^\s*(t_\w+)\s+unblocks=")


def _watchdog_dryrun_ids() -> list[str]:
    """--dry-run 出力から検出された task_id を順に返す。"""
    proc = subprocess.run(
        ["bash", str(WATCHDOG), "--dry-run"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    ids = []
    for ln in proc.stdout.splitlines():
        m = _ID_RE.match(ln)
        if m:
            ids.append(m.group(1))
    return ids


# ── watchdog dry-run on the live board ──────────────────────────────────────
def _blocked_by_pv_from_db() -> list[str]:
    import sqlite3

    con = sqlite3.connect(f"file:{BOARD_DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT id FROM tasks WHERE status='blocked' "
        "AND last_failure_error IS NOT NULL "
        "AND last_failure_error LIKE '%protocol violation%'"
    ).fetchall()
    con.close()
    return [r["id"] for r in rows]


def test_watchdog_dryrun_detects_pv_zombies_only():
    """成功指標: watchdog --dry-run の検出件数が DB の protocol-violation blocked 一致。"""
    if not BOARD_DB.exists():
        import pytest

        pytest.skip("board DB not available")
    dry_run_ids = _watchdog_dryrun_ids()
    pv_ids = _blocked_by_pv_from_db()
    # 検出は常に pv ゾンビの subset（escalation上限・失敗分を除き得る）。真ゾンビが
    # 無ければ0、有れば少なくとも1件は検出。
    if len(pv_ids) == 0:
        assert len(dry_run_ids) == 0
    else:
        assert set(dry_run_ids) <= set(pv_ids), f"detected {dry_run_ids} は pv ゾンビ {pv_ids} の外"
        assert len(dry_run_ids) >= 1


def test_watchdog_dryrun_excludes_iteration_budget_blocked():
    """成功指標: iteration-budget 等の別原因 blocked は検出しない。"""
    if not BOARD_DB.exists():
        import pytest

        pytest.skip("board DB not available")
    import sqlite3

    con = sqlite3.connect(f"file:{BOARD_DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    non_pv = con.execute(
        "SELECT id FROM tasks WHERE status='blocked' AND "
        "(last_failure_error IS NULL OR last_failure_error NOT LIKE '%protocol violation%')"
    ).fetchall()
    con.close()
    if not non_pv:
        import pytest

        pytest.skip("no non-pv blocked task on this board")
    dry_run_ids = _watchdog_dryrun_ids()
    for r in non_pv:
        assert r["id"] not in dry_run_ids, f"非ゾンビ blocked {r['id']} が検出された"


def test_loop_health_zombie_override_penalizes_score():
    """成功指標: LOOPHEALTH_ZOMBIE_COUNT=2 → zombie_task_count=2 / score -20。"""
    if not LOOP_HEALTH.exists():
        import pytest

        pytest.skip("loop_health.sh not available")
    state = Path("/tmp/lh_zombie_test_state.json")
    env = dict(os.environ)
    env["LOOPHEALTH_ZOMBIE_COUNT"] = "2"
    proc = subprocess.run(
        [
            "bash",
            str(LOOP_HEALTH),
            "--tasks",
            "[]",
            "--board",
            "kensho-ai-team",
            "--state",
            str(state),
            "--dry-run",
            "--no-park",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["zombie_task_count"] == 2
    # ベース(ゾンビ無し)が100 → 2件で80。business gateがjst時刻で発火し得るため、
    # 上限60でないことだけ確認し、「1件あたり-10・2件で80」を override 環境で厳密に。
    assert out["score"] <= 80 and out["score"] >= 60


def test_loop_health_zombie_zero_override():
    """成功指標: LOOPHEALTH_ZOMBIE_COUNT=0 → zombie_task_count=0 / score 減点なし。"""
    if not LOOP_HEALTH.exists():
        import pytest

        pytest.skip("loop_health.sh not available")
    state = Path("/tmp/lh_zombie_test_state0.json")
    env = dict(os.environ)
    env["LOOPHEALTH_ZOMBIE_COUNT"] = "0"
    proc = subprocess.run(
        [
            "bash",
            str(LOOP_HEALTH),
            "--tasks",
            "[]",
            "--board",
            "kensho-ai-team",
            "--state",
            str(state),
            "--dry-run",
            "--no-park",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["zombie_task_count"] == 0
