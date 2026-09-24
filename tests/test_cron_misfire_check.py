"""scripts/cron_misfire_check.py の回帰テスト（2026-09-25 / 無音欠火検知）。

実事故（kensho-non-api-revenue-hunter が 2026-09-24 16:00 の火を痕跡ゼロで落とし、
収益カード供給が1日停止）を再現できる粒度で固定する。
"""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import cron_misfire_check as cmc  # noqa: E402

JST = dt.timezone(dt.timedelta(hours=9))


def _write_jobs(path: Path, jobs: list[dict]) -> None:
    path.write_text(json.dumps({"jobs": jobs}, ensure_ascii=False), encoding="utf-8")


def _make_db(path: Path, rows: list[tuple]) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        "create table executions (id text, job_id text, source text, process_id text, pid int,"
        " process_started_at int, status text, claimed_at text, started_at text, finished_at text,"
        " error text, handoff_pending int, handoff_started_at text, delivery_outcome text,"
        " scheduled_instant text)"
    )
    conn.executemany(
        "insert into executions (id, job_id, source, status, claimed_at, started_at, finished_at,"
        " scheduled_instant) values (?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    conn.close()


def _job(job_id: str, expr: str, last_run: str) -> dict:
    return {
        "id": job_id,
        "name": f"job-{job_id}",
        "enabled": True,
        "state": "scheduled",
        "schedule": {"kind": "cron", "expr": expr, "display": expr},
        "last_run_at": last_run,
        "last_status": "ok",
    }


def test_daily_job_missing_fire_is_high(tmp_path: Path) -> None:
    """日次jobの火が痕跡ゼロ → severity=high / missed=1。"""
    jobs = tmp_path / "jobs.json"
    db = tmp_path / "executions.db"
    _write_jobs(jobs, [_job("deadbeef0001", "0 16 * * *", "2026-09-23T16:00:30+09:00")])
    _make_db(db, [("e1", "deadbeef0001", "builtin", "completed", None, "2026-09-23T16:00:30+09:00", None, None)])
    findings = cmc.check_profile(
        "p",
        jobs,
        db,
        as_of=dt.datetime(2026, 9, 25, 3, 50, tzinfo=JST),
        lookback_hours=48,
        grace_minutes=120,
    )
    assert len(findings) == 1
    assert findings[0]["severity"] == "high"
    assert findings[0]["missed_count"] == 1
    assert findings[0]["missed_samples"][0].startswith("2026-09-24T16:00")


def test_started_execution_covers_fire(tmp_path: Path) -> None:
    """started_at がある実行は covered（欠火にしない）。"""
    jobs = tmp_path / "jobs.json"
    db = tmp_path / "executions.db"
    _write_jobs(jobs, [_job("deadbeef0002", "0 16 * * *", "2026-09-24T16:00:10+09:00")])
    _make_db(
        db,
        [
            ("e1", "deadbeef0002", "builtin", "completed", None, "2026-09-24T16:00:10+09:00", None, None),
            ("e2", "deadbeef0002", "builtin", "failed", None, "2026-09-25T16:00:20+09:00", None, None),
        ],
    )
    findings = cmc.check_profile(
        "p",
        jobs,
        db,
        as_of=dt.datetime(2026, 9, 25, 20, 0, tzinfo=JST),
        lookback_hours=48,
        grace_minutes=120,
    )
    assert findings == []


def test_claimed_without_started_counts_as_missed(tmp_path: Path) -> None:
    """scheduled_instant 一致 + started_at NULL（claim のみ）→ 欠火扱い + unverified 計上。

    実例: d340ec02d57e が 2026-09-24 22:00 の火で claimed 00:44 / started NULL /
    status=unknown。doctor は「catch-up で走った」と誤って報告する。
    """
    jobs = tmp_path / "jobs.json"
    db = tmp_path / "executions.db"
    _write_jobs(jobs, [_job("deadbeef0003", "0 22 * * *", "2026-09-23T22:06:32+09:00")])
    _make_db(
        db,
        [
            ("e1", "deadbeef0003", "builtin", "completed", None, "2026-09-23T22:06:32+09:00", None, None),
            (
                "e2",
                "deadbeef0003",
                "builtin",
                "unknown",
                "2026-09-25T00:44:14+09:00",
                None,
                "2026-09-25T00:47:35+09:00",
                "2026-09-24T13:00:00+00:00",  # = 2026-09-24 22:00 JST
            ),
        ],
    )
    findings = cmc.check_profile(
        "p",
        jobs,
        db,
        as_of=dt.datetime(2026, 9, 25, 3, 50, tzinfo=JST),
        lookback_hours=48,
        grace_minutes=120,
    )
    assert len(findings) == 1
    assert findings[0]["severity"] == "high"
    assert findings[0]["missed_count"] == 1
    assert findings[0]["unverified_claims"] == 1


def test_single_late_run_is_silent(tmp_path: Path) -> None:
    """遅延実行1回（grace後）は late 扱いで、しきい値未満なので黙る（誤警報を出さない）。"""
    jobs = tmp_path / "jobs.json"
    db = tmp_path / "executions.db"
    _write_jobs(jobs, [_job("deadbeef0004", "0 22 * * *", "2026-09-23T22:00:05+09:00")])
    _make_db(
        db,
        [
            ("e1", "deadbeef0004", "builtin", "completed", None, "2026-09-23T22:00:05+09:00", None, None),
            ("e2", "deadbeef0004", "builtin", "completed", None, "2026-09-25T00:44:16+09:00", None, None),
        ],
    )
    findings = cmc.check_profile(
        "p",
        jobs,
        db,
        as_of=dt.datetime(2026, 9, 25, 3, 50, tzinfo=JST),
        lookback_hours=24,
        grace_minutes=120,
    )
    assert findings == []


def test_repeated_late_runs_reported_as_low(tmp_path: Path) -> None:
    """遅延実行が3回以上 → severity=low で可視化（missed は0のまま）。"""
    jobs = tmp_path / "jobs.json"
    db = tmp_path / "executions.db"
    _write_jobs(jobs, [_job("deadbeef0006", "0 */6 * * *", "2026-09-24T06:00:05+09:00")])
    _make_db(
        db,
        [
            ("e1", "deadbeef0006", "builtin", "completed", None, "2026-09-24T06:00:05+09:00", None, None),
            ("e2", "deadbeef0006", "builtin", "completed", None, "2026-09-25T01:00:00+09:00", None, None),
        ],
    )
    findings = cmc.check_profile(
        "p",
        jobs,
        db,
        as_of=dt.datetime(2026, 9, 25, 3, 50, tzinfo=JST),
        lookback_hours=24,
        grace_minutes=30,
    )
    assert len(findings) == 1
    assert findings[0]["severity"] == "low"
    assert findings[0]["missed_count"] == 0
    assert findings[0]["late_count"] == 3


def test_builtin_cron_parser_matches_croniter() -> None:
    """croniter 非依存実装が、実運用の全 cron 式で croniter と一致する（実測突合）。

    2026-09-25 実測: kensho の全ジョブ式で完全一致。croniter は hermes venv にしか
    入っていないため、cron 最小PATH配下で watchdog から呼んでも検知が止まらないよう
    フォールバックを持つ（これが無いと「監視が動いていない」状態に戻る）。
    """
    jobs_path = Path("/home/atushi/.hermes/profiles/kensho-sweeps/cron/jobs.json")
    if not jobs_path.exists():
        pytest.skip("kensho-sweeps の jobs.json が無い環境")
    croniter_mod = pytest.importorskip("croniter")
    start = dt.datetime(2026, 9, 23, 0, 0, tzinfo=JST)
    end = start + dt.timedelta(hours=48)
    exprs = sorted(
        {
            str((j.get("schedule") or {}).get("expr"))
            for j in cmc._load_jobs(jobs_path)
            if (j.get("schedule") or {}).get("kind") == "cron" and (j.get("schedule") or {}).get("expr")
        }
    )
    assert exprs, "cron 式が1件も取れていない（jobs.json の読み取り失敗）"
    for expr in exprs:
        itr = croniter_mod.croniter(expr, start - dt.timedelta(seconds=1))
        expected: list[dt.datetime] = []
        cursor = itr.get_next(dt.datetime)
        while cursor <= end and len(expected) < 1000:
            expected.append(cursor)
            cursor = itr.get_next(dt.datetime)
        assert cmc._cron_instants_builtin(expr, start, end) == expected, f"croniter と不一致: {expr}"


def test_builtin_parser_daily_and_weekly() -> None:
    """日次/週次の代表式が組込パーサで期待どおりの時刻列になる。"""
    start = dt.datetime(2026, 9, 23, 0, 0, tzinfo=JST)
    end = dt.datetime(2026, 9, 25, 0, 0, tzinfo=JST)
    daily = cmc._cron_instants_builtin("0 16 * * *", start, end)
    assert [d.strftime("%m-%d %H:%M") for d in daily] == ["09-23 16:00", "09-24 16:00"]
    hourly = cmc._cron_instants_builtin("20 * * * *", start, start + dt.timedelta(hours=2, minutes=30))
    assert [d.strftime("%H:%M") for d in hourly] == ["00:20", "01:20", "02:20"]


def test_main_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """欠火あり=exit1 / なし=exit0（ゲートとして使えること）。"""
    jobs = tmp_path / "jobs.json"
    db = tmp_path / "executions.db"
    _write_jobs(jobs, [_job("deadbeef0005", "0 16 * * *", "2026-09-23T16:00:30+09:00")])
    _make_db(db, [("e1", "deadbeef0005", "builtin", "completed", None, "2026-09-23T16:00:30+09:00", None, None)])
    base = ["--jobs", str(jobs), "--db", str(db), "--lookback-hours", "48", "--grace-minutes", "120"]
    assert cmc.main(base + ["--as-of", "2026-09-25T03:50:00+09:00"]) == 1
    assert "無音欠火" in capsys.readouterr().out
    assert cmc.main(base + ["--as-of", "2026-09-23T20:00:00+09:00"]) == 0
