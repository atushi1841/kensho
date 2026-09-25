#!/usr/bin/env python3
"""kanban_crash_breaker.py — 盤面側クラッシュループ遮断器（kensho リポジトリ内で完結）

## なぜ必要か（2026-09-24 実測 / t_5ecf88bf）
hermes core の clean-exit protocol violation（worker が rc=0 で終端 kanban 呼出なしに終了）は
`hermes_cli/kanban_db.py:9026-9035` で **意図的に** `_record_task_failure` をスキップされる。
そのため 10 回 crash しても `consecutive_failures` は 0 のままで、failure_limit ベースの
breaker は絶対に発火しない（`force_trip` も呼出元ゼロの死コード）。
shipped breaker が効かない以上、盤面側で crashed 累積を数えて park するしかない。

実測（2026-09-25 09:4x JST / kensho-ai-team 24h 窓）:
  crashed_total=250 / max_crashes_per_task=64 / completed=45
  → 1 枚のカードが枠を占有し、他の ready カードが 1 run も回らない。

## subcommands
  stats  … 24h の crash / 浪費時間 / 未着手 ready を **1 行 JSON** で出力（検証コマンドの実体）
  run    … 閾値超過カードを `hermes kanban schedule`（= park）して枠独占を止める

## 安全弁
  * DB は **read-only URI** で開く（盤面 DB を直接書き換えない。park は hermes CLI 経由）
  * kill switch: `~/.hermes/kanban/.crash_breaker.disabled` が存在すれば何もしない
  * `CRASH_BREAKER_DRY_RUN=1` で park せず判定だけ
  * **live claim 保護**: running カードは claim が失効している時だけ park（稼働中 worker を殺さない）
  * 判定ロジックと CLI を 1 ファイルに同居させ、pytest から直接 import してテストする
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

DEFAULT_BOARD = "kensho-ai-team"
DEFAULT_THRESHOLD = 3
DEFAULT_WINDOW_H = 24
DEFAULT_HERMES_BIN = "/home/atushi/.hermes/hermes-agent/venv/bin/hermes"
DEFAULT_DISABLE_FILE = "~/.hermes/kanban/.crash_breaker.disabled"
PARKABLE_STATUSES = ("ready", "running")
WASTE_OUTCOMES = ("crashed", "reclaimed")


def _env_int(name: str, default: int) -> int:
    """環境変数を int として読む。未設定・不正値は default。"""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def board_db_path() -> str:
    """盤面 DB の絶対パス。KANBAN_DB 明示 > boards/<board>/kanban.db。

    旧 kanban_crash_stats.sh は `/home/atushi/.hermes/kanban/kanban.db`（存在しない）を
    見ていたため、常に空結果になっていた（2026-09-25 実測）。
    """
    explicit = os.environ.get("KANBAN_DB", "").strip()
    if explicit:
        return explicit
    board = os.environ.get("KANBAN_BOARD", "").strip() or DEFAULT_BOARD
    return str(Path.home() / ".hermes" / "kanban" / "boards" / board / "kanban.db")


def connect_ro(db: str) -> sqlite3.Connection:
    """読み取り専用で接続する（共有盤面 DB への書き込み禁止）。"""
    return sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=15)


def collect_stats(db: str, window_h: int, now: int | None = None) -> dict[str, Any]:
    """24h 窓の crash 統計を集計して返す。"""
    now_ts = int(time.time()) if now is None else int(now)
    since = now_ts - window_h * 3600
    con = connect_ro(db)
    try:
        runs = con.execute(
            "SELECT task_id, profile, outcome, started_at, ended_at "
            "FROM task_runs WHERE started_at >= ?",
            (since,),
        ).fetchall()
        tasks = {
            str(r[0]): {"assignee": r[1], "status": r[2], "claim_expires": r[3]}
            for r in con.execute("SELECT id, assignee, status, claim_expires FROM tasks")
        }
    finally:
        con.close()

    crashes: dict[str, int] = {}
    waste_by_profile: dict[str, int] = {}
    total_by_profile: dict[str, int] = {}
    runs_by_task: dict[str, int] = {}

    for task_id, profile, outcome, started_at, ended_at in runs:
        tid = str(task_id)
        prof = str(profile or "?")
        start = int(started_at or 0)
        end = int(ended_at) if ended_at not in (None, "") else now_ts
        dur = max(0, end - start)
        total_by_profile[prof] = total_by_profile.get(prof, 0) + dur
        runs_by_task[tid] = runs_by_task.get(tid, 0) + 1
        if outcome == "crashed":
            crashes[tid] = crashes.get(tid, 0) + 1
        if outcome in WASTE_OUTCOMES:
            waste_by_profile[prof] = waste_by_profile.get(prof, 0) + dur

    total_dur = sum(total_by_profile.values())
    waste_dur = sum(waste_by_profile.values())
    waste_by_profile_pct = {
        prof: round(100.0 * waste_by_profile.get(prof, 0) / dur, 1)
        for prof, dur in sorted(total_by_profile.items())
        if dur > 0
    }

    top_tasks = []
    for tid, count in sorted(crashes.items(), key=lambda kv: (-kv[1], kv[0]))[:10]:
        meta = tasks.get(tid, {})
        claim_expires = meta.get("claim_expires")
        top_tasks.append(
            {
                "id": tid,
                "profile": meta.get("assignee"),
                "crashes": count,
                "status": meta.get("status"),
                "claim_expired": claim_expires is None or int(claim_expires or 0) <= now_ts,
            }
        )

    ready_zero_run = sum(
        1
        for tid, meta in tasks.items()
        if meta.get("status") == "ready" and tid not in runs_by_task
    )

    return {
        "window_h": window_h,
        "crashed_total": sum(crashes.values()),
        "max_crashes_per_task": max(crashes.values()) if crashes else 0,
        "waste_ratio_pct": round(100.0 * waste_dur / total_dur, 1) if total_dur else 0.0,
        "ready_zero_run": ready_zero_run,
        "top_tasks": top_tasks,
        "waste_by_profile_pct": waste_by_profile_pct,
    }


def select_candidates(stats: dict[str, Any], threshold: int, now: int | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """park 対象と「live claim 保護で見送った」カードを返す。

    running のまま park すると稼働中 worker の成果を捨てることになるため、
    claim が失効している時だけ running を対象にする（実測 2026-09-25: running 3 枚は
    すべて live claim だった）。
    """
    _ = now
    parkable: list[dict[str, Any]] = []
    skipped_live: list[dict[str, Any]] = []
    for row in stats.get("top_tasks", []):
        if int(row.get("crashes", 0)) < threshold:
            continue
        status = row.get("status")
        if status == "ready":
            parkable.append(row)
        elif status == "running":
            if row.get("claim_expired"):
                parkable.append(row)
            else:
                skipped_live.append(row)
    return parkable, skipped_live


def park_task(tid: str, reason: str, hermes_bin: str, board: str) -> tuple[int, str]:
    """hermes CLI 経由でカードを park する。戻り値 (returncode, stdout+stderr)。"""
    cmd = [hermes_bin, "kanban", "--board", board, "schedule", tid, reason]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def append_log(path: str, line: str) -> None:
    if not path:
        return
    try:
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(line.rstrip("\n") + "\n")
    except OSError:
        pass


def cmd_stats() -> int:
    db = board_db_path()
    window_h = _env_int("CRASH_STATS_WINDOW_H", DEFAULT_WINDOW_H)
    if not Path(db).exists():
        print(json.dumps({"error": "db_not_found", "db": db}, ensure_ascii=False))
        return 1
    stats = collect_stats(db, window_h)
    stats["db"] = db
    print(json.dumps(stats, ensure_ascii=False))
    return 0


def cmd_run() -> int:
    board = os.environ.get("KANBAN_BOARD", "").strip() or DEFAULT_BOARD
    db = board_db_path()
    window_h = _env_int("CRASH_BREAKER_WINDOW_H", DEFAULT_WINDOW_H)
    threshold = _env_int("CRASH_BREAKER_THRESHOLD", DEFAULT_THRESHOLD)
    dry_run = _env_flag("CRASH_BREAKER_DRY_RUN")
    hermes_bin = os.environ.get("HERMES_BIN", "").strip() or DEFAULT_HERMES_BIN
    disable_file = Path(
        os.environ.get("CRASH_BREAKER_DISABLE_FILE", "").strip() or DEFAULT_DISABLE_FILE
    ).expanduser()

    if disable_file.exists():
        print(json.dumps({"breaker": "skipped", "reason": "disabled", "file": str(disable_file)}, ensure_ascii=False))
        return 0
    if not Path(db).exists():
        print(json.dumps({"breaker": "skipped", "reason": "db_not_found", "db": db}, ensure_ascii=False))
        return 0

    stats = collect_stats(db, window_h)
    parkable, skipped_live = select_candidates(stats, threshold)

    parked: list[str] = []
    failed: list[dict[str, str]] = []
    details: list[dict[str, Any]] = []
    for row in parkable:
        tid = str(row["id"])
        reason = (
            f"crash-loop breaker: {row['crashes']} crashes/{window_h}h (threshold={threshold}) — "
            f"枠独占を止めるため park。再開は hermes kanban promote {tid}"
        )
        if dry_run:
            details.append({"id": tid, "crashes": row["crashes"], "action": "dry-run"})
            continue
        rc, out = park_task(tid, reason, hermes_bin, board)
        if rc == 0:
            parked.append(tid)
            details.append({"id": tid, "crashes": row["crashes"], "action": "parked"})
        else:
            failed.append({"id": tid, "rc": str(rc), "out": out.strip()[:200]})
            details.append({"id": tid, "crashes": row["crashes"], "action": "failed", "rc": rc})

    summary = {
        "breaker": "dry_run" if dry_run else "ran",
        "window_h": window_h,
        "threshold": threshold,
        "crashed_total": stats["crashed_total"],
        "max_crashes_per_task": stats["max_crashes_per_task"],
        "waste_ratio_pct": stats["waste_ratio_pct"],
        "candidates": len(parkable),
        "parked": len(parked),
        "parked_ids": parked,
        "failed": failed,
        "skipped_live_claim": [r["id"] for r in skipped_live],
    }
    log_path = os.environ.get("CRASH_BREAKER_LOG", "").strip() or str(
        Path("/mnt/d/Project2/kensho/data/crash_breaker.log")
    )
    append_log(log_path, f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {json.dumps(summary, ensure_ascii=False)}")
    # 何も park しなかった平常時は無音（no_agent cron の stdout を汚さない）
    if not parked and not failed:
        return 0
    print(json.dumps(summary, ensure_ascii=False))
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in ("stats", "run"):
        sys.stderr.write("usage: kanban_crash_breaker.py {stats|run}\n")
        return 2
    return cmd_stats() if argv[1] == "stats" else cmd_run()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
