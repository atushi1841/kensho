"""loop_health.sh top_task 不変条件テスト (v137 / t_296c3dbc).

QA 9/12実測: by_age は started_at 昇順(先頭=最古)なのに top_task=by_age[-1] が
最新規を拾っており、running 2件以上で park/escalation target が最古でなく最新に
なっていた（SLA parking 空振り）。本テストで不変条件「top_task=最古running」を固定。
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "loop_health.sh"

NOW_TS = int(datetime.now().timestamp())
OLDEST_ID = "t_oldest01"
NEWEST_ID = "t_newest01"


def _run_loop_health(tmp_path: Path, tasks: list) -> dict:
    """Run loop_health.sh with an injected task list, side-effect free."""
    state_file = tmp_path / "loop_health_state.json"
    proc = subprocess.run(
        [
            "bash",
            str(SCRIPT),
            "--tasks",
            json.dumps(tasks),
            "--board",
            "kensho-ai-team",
            "--state",
            str(state_file),
            "--dry-run",
            "--no-park",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, f"loop_health.sh failed: {proc.stderr}"
    return json.loads(proc.stdout)


def _running_tasks():
    """2件以上running fixture: 10時間前スタート最古規 + 1時間前スタート最新規."""
    return [
        {
            "id": OLDEST_ID,
            "status": "running",
            "title": "oldest running task",
            "started_at": NOW_TS - 10 * 3600,
            "result": None,
        },
        {
            "id": NEWEST_ID,
            "status": "running",
            "title": "newest running task",
            "started_at": NOW_TS - 1 * 3600,
            "result": None,
        },
    ]


def test_top_task_is_oldest_running(tmp_path: Path) -> None:
    """成功指標: running 2件(10h前/1h前)で top_task == 10h前タスクID."""
    out = _run_loop_health(tmp_path, _running_tasks())
    assert out["top_task"] == OLDEST_ID
    assert out["escalation_target"] == OLDEST_ID
    # lines表示の top= 行も最古IDと一致（park target導出と同一経路）
    top_line = next(line for line in out["lines"] if line.startswith("top="))
    assert top_line.startswith(f"top={OLDEST_ID}")


def test_top_task_single_running(tmp_path: Path) -> None:
    """後方互換: running 1件なら従来通りそのタスクがtop_task."""
    tasks = _running_tasks()[:1]
    out = _run_loop_health(tmp_path, tasks)
    assert out["top_task"] == OLDEST_ID


def test_no_running_top_task_none(tmp_path: Path) -> None:
    """running 0件（blockedのみ）なら top_task=null で落ちない."""
    tasks = [
        {
            "id": "t_blocked01",
            "status": "blocked",
            "title": "blocked only",
            "started_at": NOW_TS - 30 * 3600,
            "result": "waiting",
        }
    ]
    out = _run_loop_health(tmp_path, tasks)
    assert out["top_task"] is None
    assert out["running"] == 0


def test_aux_auth_errors_detected(tmp_path: Path) -> None:
    """Success metric: fake 401 error in errors.log triggers alert."""
    import os
    from datetime import datetime, timedelta
    # Inject 10 fake auxiliary auth errors into a temporary errors.log, spread over the last 5 minutes
    log_path = tmp_path / "errors.log"
    now = datetime.now()
    lines = []
    for i in range(10):
        ts = now - timedelta(minutes=5, seconds=i*10)  # within the last 5 minutes
        # Format as: YYYY-MM-DD HH:MM:SS,mmm
        log_line = ts.strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]  # trim to milliseconds
        lines.append(f"{log_line} WARNING agent.auxiliary_client: Auxiliary kanban_decomposer: auth error on auto and all fallbacks exhausted\\n")
    log_path.write_text("".join(lines))
    # Use env var to override the log path
    env = os.environ.copy()
    env["LOOPHEALTH_AUX_LOG_PATH"] = str(log_path)
    env["LOOPHEALTH_JST_HOUR"] = "3"  # disable business KPI gate (no_action_window 00:00-07:00)
    out = subprocess.run(
        ["bash", str(SCRIPT), "--board", "kensho-ai-team", "--dry-run", "--no-park"],
        capture_output=True,
        text=True,
        env=env,
        cwd=REPO_ROOT,
    ).stdout
    data = json.loads(out)
    # Expect aux_auth_errors >= 10 to trigger ERROR alert
    assert data.get("aux_auth_errors", 0) >= 10, f"Expected >=10 aux_auth_errors, got {data.get('aux_auth_errors')}"
    assert data["alert"] == "ALERT", f"Expected ALERT, got {data['alert']}"
