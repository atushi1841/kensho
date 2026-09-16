"""kensho_script_drift_check / kensho_script_drift_watch テスト (t_20c9c446 / QA run508提案).

背景事故: 5f32176（apify_run_monitor.py）は repo に正しく入っていたが cron 配置は
03:57版のまま = 方式A不発。検出は existed する朝1回の drift-check しかなく、
5分監視（ai-context-monitor.sh 統合）と monitor_script 走査を追加した。

不変条件:
  1. check: script と monitor_script 参照の両方を DRIFT/MISSING 検査する（過去は script のみ）
  2. watch: 漂移時に DRIFT-WATCH 行を stdout へ出す / cp同期後は無出力（サイレント監視）
  3. watch: 同一 script の通知dedup（2回連続漂移で再通知しない）+ 解消後の再漂移で再通知
  4. watch: 検出基盤異常でも exit 0（呼び出し側 monitor を止めない）
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECK = REPO_ROOT / "scripts" / "kensho_script_drift_check.py"
WATCH = REPO_ROOT / "scripts" / "kensho_script_drift_watch.py"


def _fixture(tmp_path: Path) -> dict:
    """profiles/testprof/{cron,scripts} + repo/scripts の最小ツリーを構築。

    - dummy_job.py: DRIFT（repo=v2 / profile=v1）
    - mon_job.py:   monitor_script 参照・一致（OK）
    """
    prof = tmp_path / "profiles" / "testprof"
    (prof / "cron").mkdir(parents=True)
    (prof / "scripts").mkdir(parents=True)
    repo = tmp_path / "repo" / "scripts"
    repo.mkdir(parents=True)
    (repo / "dummy_job.py").write_text('print("v2")\n', encoding="utf-8")
    (prof / "scripts" / "dummy_job.py").write_text('print("v1-old")\n', encoding="utf-8")
    (repo / "mon_job.py").write_text('print("same")\n', encoding="utf-8")
    (prof / "scripts" / "mon_job.py").write_text('print("same")\n', encoding="utf-8")
    jobs = {
        "jobs": [
            {"id": "j1", "name": "dummy", "script": "dummy_job.py", "enabled": True},
            {"id": "j2", "name": "mon", "monitor_script": "mon_job.py", "enabled": True},
        ],
        "updated_at": "x",
    }
    jobs_file = prof / "cron" / "jobs.json"
    jobs_file.write_text(json.dumps(jobs), encoding="utf-8")
    env = {
        "DRIFT_JOBS": str(jobs_file),
        "PROFILE_SCRIPTS_ROOT": str(tmp_path / "profiles"),
        "KENSHO_ROOT": str(tmp_path / "repo"),
    }
    return {"env": env, "repo": tmp_path / "repo", "prof": prof, "jobs_file": jobs_file}


def _run(script: Path, env: dict, extra: list[str] | None = None) -> subprocess.CompletedProcess:
    import os

    e = dict(os.environ)
    e.update(env)
    return subprocess.run(
        [sys.executable, str(script), *(extra or [])],
        capture_output=True,
        text=True,
        env=e,
        timeout=60,
    )


class TestCheckMonitorScriptCoverage:
    def test_monitor_script_drift_is_detected(self, tmp_path):
        """monitor_script 参照の漂移も FAIL 化する（従来は script 参照だけ走査）。"""
        fx = _fixture(tmp_path)
        mon = fx["prof"] / "scripts" / "mon_job.py"
        mon.write_text('print("drifted")\n', encoding="utf-8")
        proc = _run(CHECK, fx["env"])
        assert proc.returncode == 0
        assert "DRIFT" in proc.stdout
        assert "mon_job.py" in proc.stdout

    def test_all_synced_is_silent(self, tmp_path):
        fx = _fixture(tmp_path)
        (fx["prof"] / "scripts" / "dummy_job.py").write_text('print("v2")\n', encoding="utf-8")
        proc = _run(CHECK, fx["env"])
        assert proc.returncode == 0
        assert proc.stdout.strip() == ""

    def test_json_counts_monitor_reference(self, tmp_path):
        fx = _fixture(tmp_path)
        proc = _run(CHECK, fx["env"], ["--json"])
        data = json.loads(proc.stdout.strip().splitlines()[-1])
        names = {f["script"] for f in data["fails"]}
        assert names == {"dummy_job.py"}
        assert data["checked"] == 2  # script+monitor_script 両方走査対象


class TestWatchIntegration:
    def test_drift_prints_one_line(self, tmp_path):
        fx = _fixture(tmp_path)
        env = dict(fx["env"])
        env["DRIFT_CHECK_PY"] = str(CHECK)
        proc = _run(
            WATCH,
            env,
            ["--no-notify", "--state", str(tmp_path / "s.json"), "--log", str(tmp_path / "l.txt")],
        )
        assert proc.returncode == 0
        lines = proc.stdout.strip().splitlines()
        assert len(lines) == 1 and "DRIFT-WATCH" in lines[0] and "dummy_job.py" in lines[0]

    def test_synced_is_silent(self, tmp_path):
        fx = _fixture(tmp_path)
        (fx["prof"] / "scripts" / "dummy_job.py").write_text('print("v2")\n', encoding="utf-8")
        env = dict(fx["env"])
        env["DRIFT_CHECK_PY"] = str(CHECK)
        args = ["--no-notify", "--state", str(tmp_path / "s.json"), "--log", str(tmp_path / "l.txt")]
        first = _run(WATCH, env, args)
        assert first.returncode == 0
        assert first.stdout.strip() == ""

    def test_notify_dedup_and_renotification(self, tmp_path):
        """同一漂移は通知1回だけ。解消→再漂移で state クリア→再通知候補に戻る。"""
        fx = _fixture(tmp_path)
        env = dict(fx["env"])
        env["DRIFT_CHECK_PY"] = str(CHECK)
        state = tmp_path / "s.json"
        log = tmp_path / "l.txt"
        args = ["--no-notify", "--state", str(state), "--log", str(log)]
        _run(WATCH, env, args)  # 1回目 WARN
        _run(WATCH, env, args)  # 2回目: 同一なら state は増えない
        st = json.loads(state.read_text(encoding="utf-8"))
        assert list(st["notified"].keys()) == ["DRIFT:dummy_job.py"]
        # cp同期 → RESOLVEDで state の該当キー除去
        (fx["prof"] / "scripts" / "dummy_job.py").write_text('print("v2")\n', encoding="utf-8")
        _run(WATCH, env, args)
        st = json.loads(state.read_text(encoding="utf-8"))
        assert "DRIFT:dummy_job.py" not in st["notified"]
        # 再漂移 → fresh 扱いでもう一度 WARN 行が出る
        (fx["prof"] / "scripts" / "dummy_job.py").write_text('print("v3-drift")\n', encoding="utf-8")
        proc = _run(WATCH, env, args)
        assert "DRIFT-WATCH" in proc.stdout
        assert log.read_text(encoding="utf-8").count("WARN DRIFT:dummy_job.py") == 2

    def test_broken_check_still_exit_zero(self, tmp_path):
        """check 側が壊れても exit 0（monitor を止めない・stderrにERRORのみ）。"""
        env = {"DRIFT_CHECK_PY": str(tmp_path / "nope.py")}
        proc = _run(
            WATCH,
            env,
            ["--no-notify", "--state", str(tmp_path / "s.json"), "--log", str(tmp_path / "l.txt")],
        )
        assert proc.returncode == 0
        assert "ERROR" in proc.stderr
