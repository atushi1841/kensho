#!/usr/bin/env python3
"""cron 無音欠火（silent misfire）検知 — 読み取り専用。

背景（2026-09-25 実測・t_2386ad9b の供給源が1日停止した事故）:
  kensho-non-api-revenue-hunter (458eacc3c96c, `0 16 * * *`) が 2026-09-24 16:00 の火を
  完全に落とした。executions.db にレコードが1行も残らず、cron/output/ にもファイルが無く、
  last_status=ok のまま last_run_at が前日で止まる。結果:
    - `hermes cron doctor` … 検知しない（late fire / last_error しか見ない＝「実行されて失敗」のみ）
    - kensho-cron-watchdog … 検知しない（cron_incidents を数えるだけ＝同じく失敗runのみ）
    - 収益カード供給が丸1日停止し、kensho-revenue-worker の ready が 0 件になった
  「実行されて失敗した」は誰かが見るが、「そもそも実行されなかった」を見る者が居なかった。

この検査は「スケジュール上あるべき火」と「executions に実在する実行痕跡」を突合し、
猶予（grace）を過ぎても痕跡ゼロの火を欠火として報告する。区別する3状態:
  covered … 予定時刻±grace に実行痕跡あり（正常）
  late    … 予定時刻+grace を過ぎてから実行された（遅延実行で回復。doctor の "catch-up" 相当）
  missed  … as_of まで痕跡ゼロ（**無音欠火**。これが本命）

使い方:
  python3 scripts/cron_misfire_check.py                      # 直近24h・medium以上のみ表示
  python3 scripts/cron_misfire_check.py --min-severity low    # 遅延も全部見る
  python3 scripts/cron_misfire_check.py --json
  python3 scripts/cron_misfire_check.py --as-of 2026-09-25T03:50:00+09:00 --lookback-hours 48
      # 過去時点のリプレイ（事故再現の検証に使う。2026-09-25の実例はこの形で再現済み）

終了コード: 0=min-severity以上の欠火なし / 1=あり / 2=使い方・入力エラー
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import sqlite3
import sys
from pathlib import Path

JST = dt.timezone(dt.timedelta(hours=9))
HERMES_ROOT = Path(os.environ.get("HERMES_ROOT", str(Path.home() / ".hermes")))
DEFAULT_PROFILE = os.environ.get("HERMES_PROFILE", "kensho-sweeps")
SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2}


def _parse_iso(text: str) -> dt.datetime:
    value = dt.datetime.fromisoformat(str(text))
    if value.tzinfo is None:
        value = value.replace(tzinfo=JST)
    return value


def _job_paths(profile: str) -> list[tuple[str, Path, Path]]:
    """(profile名, jobs.json, executions.db) を返す。profile=all で全プロファイル。"""
    if profile == "all":
        out: list[tuple[str, Path, Path]] = []
        for jobs in sorted(glob.glob(str(HERMES_ROOT / "profiles" / "*" / "cron" / "jobs.json"))):
            path = Path(jobs)
            out.append((path.parts[-3], path, path.parent / "executions.db"))
        return out
    base = HERMES_ROOT / "profiles" / profile / "cron"
    return [(profile, base / "jobs.json", base / "executions.db")]


def _load_jobs(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    jobs = data if isinstance(data, list) else data.get("jobs", data)
    if isinstance(jobs, dict):
        jobs = list(jobs.values())
    return [j for j in jobs if isinstance(j, dict)]


def _expand_field(field: str, lo: int, hi: int) -> set[int]:
    values: set[int] = set()
    for part in field.split(","):
        part = part.strip()
        if not part:
            continue
        step = 1
        if "/" in part:
            part, step_raw = part.split("/", 1)
            step = int(step_raw)
            if step <= 0:
                raise ValueError(f"不正なステップ: {field}")
        if part in ("*", ""):
            start, end = lo, hi
        elif "-" in part:
            start_raw, end_raw = part.split("-", 1)
            start, end = int(start_raw), int(end_raw)
        else:
            start = end = int(part)
        if start < lo or end > hi or start > end:
            raise ValueError(f"範囲外: {field}")
        values.update(range(start, end + 1, step))
    return values


def _cron_instants_builtin(expr: str, start: dt.datetime, end: dt.datetime) -> list[dt.datetime]:
    """croniter 非依存の最小5フィールド実装（分単位マッチ走査）。

    kensho のジョブで使う `0 16 * * *` / `20 * * * *` / `*/5 * * * *` 等を網羅する。
    DOM と DOW が両方制限されている場合は cron の標準どおり OR で判定する。
    """
    fields = expr.split()
    if len(fields) != 5:
        raise ValueError(f"5フィールドではない cron 式: {expr!r}")
    minutes = _expand_field(fields[0], 0, 59)
    hours = _expand_field(fields[1], 0, 23)
    doms = _expand_field(fields[2], 1, 31)
    months = _expand_field(fields[3], 1, 12)
    dows = _expand_field(fields[4], 0, 7)
    dom_restricted = fields[2].strip() != "*"
    dow_restricted = fields[4].strip() != "*"

    out: list[dt.datetime] = []
    cursor = start.replace(second=0, microsecond=0)
    if cursor < start:
        cursor += dt.timedelta(minutes=1)
    while cursor <= end and len(out) < 1000:
        if cursor.minute in minutes and cursor.hour in hours and cursor.month in months:
            dom_ok = cursor.day in doms
            dow_ok = (cursor.isoweekday() % 7) in dows
            if dom_restricted and dow_restricted:
                hit = dom_ok or dow_ok
            else:
                hit = dom_ok and dow_ok
            if hit:
                out.append(cursor)
        cursor += dt.timedelta(minutes=1)
    return out


def _expected_instants(
    job: dict, start: dt.datetime, end: dt.datetime
) -> tuple[list[dt.datetime], float]:
    """予定時刻の列と、その間隔(時間)。interval は last_run_at を位相アンカーに使う。"""
    schedule = job.get("schedule") or {}
    kind = schedule.get("kind")
    instants: list[dt.datetime] = []
    if kind == "cron" and schedule.get("expr"):
        try:
            from croniter import croniter
        except ImportError:  # croniter が無い環境でも動く（cron 無音欠火の検知を止めない）
            instants = _cron_instants_builtin(str(schedule["expr"]), start, end)
        else:
            itr = croniter(schedule["expr"], start - dt.timedelta(seconds=1))
            cursor = itr.get_next(dt.datetime)
            while cursor <= end and len(instants) < 1000:
                instants.append(cursor)
                cursor = itr.get_next(dt.datetime)
    elif kind == "interval" and schedule.get("minutes"):
        step = dt.timedelta(minutes=int(schedule["minutes"]))
        anchor_raw = job.get("last_run_at") or job.get("created_at")
        if not anchor_raw:
            return [], step.total_seconds() / 3600.0
        anchor = _parse_iso(anchor_raw)
        cursor = anchor
        while cursor > start:
            cursor -= step
        while cursor <= end and len(instants) < 1000:
            if cursor >= start:
                instants.append(cursor)
            cursor += step
    interval_h = None
    if len(instants) >= 2:
        deltas = sorted(
            (instants[i + 1] - instants[i]).total_seconds() / 3600.0
            for i in range(len(instants) - 1)
        )
        interval_h = deltas[len(deltas) // 2]
    return instants, (interval_h if interval_h else 24.0)


def _executions(db_path: Path, job_id: str) -> list[dict]:
    """その job の全実行行（scheduled_instant / started_at / claimed_at / status）。

    scheduled_instant は「どの予定火に対する実行か」を厳密に示す（実測: 2026-09-24T13:00:00+00:00
    = 22:00 JST）。claimed はされたが started_at が NULL の行は「実行痕跡なし」＝
    無音欠火と区別できないため unverified として扱う（2026-09-25 の d340ec02d57e が実例）。
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "select scheduled_instant, started_at, claimed_at, finished_at, status"
            " from executions where job_id=?",
            (job_id,),
        ).fetchall()
    finally:
        conn.close()
    out: list[dict] = []
    for sched, started, claimed, finished, status in rows:
        record: dict = {"status": status, "started": None, "claimed": None, "sched": None}
        for key, raw in (("sched", sched), ("started", started), ("claimed", claimed), ("finished", finished)):
            if not raw:
                continue
            try:
                record[key] = _parse_iso(str(raw))
            except ValueError:
                record[key] = None
        out.append(record)
    return out


def _runs(instants: list[dt.datetime], interval_h: float) -> list[list[dt.datetime]]:
    """連続する欠火を1まとまり（停止窓）に畳む。"""
    if not instants:
        return []
    gap = dt.timedelta(hours=max(interval_h * 1.5, 0.5))
    grouped: list[list[dt.datetime]] = [[instants[0]]]
    for inst in instants[1:]:
        if inst - grouped[-1][-1] <= gap:
            grouped[-1].append(inst)
        else:
            grouped.append([inst])
    return grouped


def check_profile(
    profile: str,
    jobs_path: Path,
    db_path: Path,
    *,
    as_of: dt.datetime,
    lookback_hours: float,
    grace_minutes: float,
) -> list[dict]:
    findings: list[dict] = []
    if not jobs_path.exists():
        return findings
    window_start = as_of - dt.timedelta(hours=lookback_hours)
    window_end = as_of - dt.timedelta(minutes=grace_minutes)
    for job in _load_jobs(jobs_path):
        if not job.get("enabled") or job.get("state") != "scheduled":
            continue
        job_id = str(job.get("id") or "")
        if not job_id:
            continue
        executions = _executions(db_path, job_id)
        instants, interval_h = _expected_instants(job, window_start, window_end)
        missed: list[dt.datetime] = []
        late = 0
        unverified = 0
        for instant in instants:
            low = instant - dt.timedelta(minutes=1)
            high = instant + dt.timedelta(minutes=grace_minutes)
            exact = [e for e in executions if e["sched"] == instant]
            if exact:
                # scheduled_instant で厳密対応。
                # started_at がある行＝実際に走った（成否は問わない）。
                # started_at が無い行＝claim されたが実行痕跡なし → 欠火として数える。
                if any(e["started"] is not None for e in exact):
                    continue
                unverified += 1
                missed.append(instant)
                continue
            times = [e["started"] or e["claimed"] for e in executions]
            times = [t for t in times if t is not None]
            if any(low <= t <= high for t in times):
                continue
            if any(high < t <= as_of for t in times):
                late += 1
            else:
                missed.append(instant)
        if not missed and late < 3:
            continue
        groups = _runs(missed, interval_h)
        max_run = max((len(g) for g in groups), default=0)
        if max_run == 0:
            severity = "low"
        elif interval_h >= 24.0 and max_run >= 1:
            severity = "high"  # 日次以上の間隔＝その日の機能が丸ごと落ちる
        elif max_run >= 2:
            severity = "medium"
        else:
            severity = "low"
        findings.append(
            {
                "profile": profile,
                "job_id": job_id,
                "name": job.get("name"),
                "schedule": (job.get("schedule") or {}).get("display")
                or (job.get("schedule") or {}).get("expr"),
                "interval_hours": round(interval_h, 2),
                "severity": severity,
                "missed_count": len(missed),
                "max_consecutive": max_run,
                "late_count": late,
                "unverified_claims": unverified,
                "last_run_at": job.get("last_run_at"),
                "last_status": job.get("last_status"),
                "missed_samples": [
                    m.astimezone(JST).isoformat(timespec="minutes") for m in missed[:5]
                ],
            }
        )
    findings.sort(key=lambda f: (-SEVERITY_ORDER[f["severity"]], -f["missed_count"]))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="cron 無音欠火（実行痕跡ゼロの火）を検知する（読み取り専用）"
    )
    parser.add_argument("--profile", default=DEFAULT_PROFILE, help="プロファイル名（all で全件）")
    parser.add_argument("--jobs", help="jobs.json を直接指定（--profile より優先）")
    parser.add_argument("--db", help="executions.db を直接指定")
    parser.add_argument("--lookback-hours", type=float, default=24.0)
    parser.add_argument("--grace-minutes", type=float, default=120.0)
    parser.add_argument("--as-of", help="検査基準時刻（ISO8601・過去時点のリプレイ用）")
    parser.add_argument("--min-severity", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    try:
        as_of = _parse_iso(args.as_of) if args.as_of else dt.datetime.now(JST)
    except ValueError as exc:
        print(f"時刻の解釈に失敗: {exc}", file=sys.stderr)
        return 2

    if args.jobs:
        jobs_path = Path(args.jobs)
        targets = [("explicit", jobs_path, Path(args.db) if args.db else jobs_path.parent / "executions.db")]
    else:
        targets = _job_paths(args.profile)

    findings: list[dict] = []
    for profile, jobs_path, db_path in targets:
        findings.extend(
            check_profile(
                profile,
                jobs_path,
                db_path,
                as_of=as_of,
                lookback_hours=args.lookback_hours,
                grace_minutes=args.grace_minutes,
            )
        )
    findings.sort(key=lambda f: (-SEVERITY_ORDER[f["severity"]], -f["missed_count"]))
    shown = [f for f in findings if SEVERITY_ORDER[f["severity"]] >= SEVERITY_ORDER[args.min_severity]]
    total = sum(f["missed_count"] for f in findings)

    if args.as_json:
        print(
            json.dumps(
                {
                    "as_of": as_of.isoformat(timespec="seconds"),
                    "lookback_hours": args.lookback_hours,
                    "grace_minutes": args.grace_minutes,
                    "profile_count": len(targets),
                    "missed_fires": total,
                    "finding_count": len(shown),
                    "findings": [f for f in findings if SEVERITY_ORDER[f["severity"]] >= SEVERITY_ORDER[args.min_severity]],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1 if shown else 0

    if not shown:
        print(
            f"[cron-misfire] 欠火なし（min-severity={args.min_severity} "
            f"as_of={as_of.isoformat(timespec='minutes')} lookback={args.lookback_hours}h "
            f"grace={args.grace_minutes}m 対象={len(targets)}profile 総missed={total}）"
        )
        return 0

    print(
        f"⚠️ cron 無音欠火 {len(shown)}ジョブ / 計{sum(f['missed_count'] for f in shown)}回 "
        f"（min-severity={args.min_severity} as_of={as_of.isoformat(timespec='minutes')} "
        f"lookback={args.lookback_hours}h grace={args.grace_minutes}m）"
    )
    for f in shown:
        print(
            f"  [{f['severity']}] {f['job_id']} {f['name']} ({f['schedule']}, 間隔{f['interval_hours']}h) "
            f"missed={f['missed_count']}回 連続最大{f['max_consecutive']} 遅延回復={f['late_count']}回 "
            f"claim無実行={f['unverified_claims']}回 "
            f"例={f['missed_samples']} last_run={f['last_run_at']}"
        )
    print("  対処: `hermes cron run <job_id>` で取り戻し実行し、欠火の原因を調べる")
    return 1


if __name__ == "__main__":
    sys.exit(main())
