#!/usr/bin/env python3
"""Kanban AIチーム 日次実績レポート — done/crashed/timed_out の集計と失敗原因 Top5。

Kanban SQLite から前日(JST)の task_runs を集計し、構造化 JSON で stdout にする。
daily_pipeline_report.py がこの出力をマージして Telegram 通知に詰める。

使い方:
    python3 kensho/tools/kanban_report.py [YYYY-MM-DD]
    python3 kensho/tools/kanban_report.py --json [YYYY-MM-DD]
"""
from __future__ import annotations

import collections
import datetime
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
KANBAN_DB = Path.home() / ".hermes" / "kanban" / "boards" / "kensho-ai-team" / "kanban.db"
JST = datetime.timezone(datetime.timedelta(hours=9))

# 失敗として集計する run status
FAIL_STATUSES = ("crashed", "timed_out", "gave_up")
OK_STATUSES = ("completed", "done")


def _target_date() -> str:
    if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        return sys.argv[1]
    return (datetime.datetime.now(JST) - datetime.timedelta(days=1)).strftime("%Y-%m-%d")


def _jst_range(date_s: str) -> tuple[int, int]:
    d0 = datetime.datetime.strptime(date_s, "%Y-%m-%d").replace(tzinfo=JST)
    d1 = d0 + datetime.timedelta(days=1)
    return int(d0.timestamp()), int(d1.timestamp())


def collect(date_s: str) -> dict:
    if not KANBAN_DB.exists():
        return {"date": date_s, "error": "kanban.db not found", "runs": 0}
    t0, t1 = _jst_range(date_s)
    conn = sqlite3.connect(str(KANBAN_DB))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT status, profile, error, outcome FROM task_runs "
            "WHERE started_at >= ? AND started_at < ?",
            (t0, t1),
        ).fetchall()
    finally:
        conn.close()

    by_status: dict[str, int] = collections.Counter()
    by_profile: dict[str, int] = collections.Counter()
    fail_reasons: collections.Counter = collections.Counter()
    fail_by_profile: dict[str, collections.Counter] = collections.defaultdict(
        collections.Counter
    )

    for r in rows:
        st = r["status"] or "?"
        by_status[st] += 1
        by_profile[r["profile"] or "?"] += 1
        if st in FAIL_STATUSES:
            err = r["error"] or ""
            # protocol violation は同一シグネチャに正規化
            if "protocol violation" in err or "worker exited cleanly" in err:
                key = "rc=0 protocol violation (kanban_complete未呼び出し)"
            elif "Iteration budget" in err:
                key = "Iteration budget exhausted (90/90)"
            elif "pid" in err and "not alive" in err:
                key = "worker pid gone (kill/早期終了)"
            elif "exited with code 1" in err:
                key = "worker exited code 1"
            else:
                key = err[:80] or "(no message)"
            fail_reasons[key] += 1
            fail_by_profile[r["profile"] or "?"][key] += 1

    return {
        "date": date_s,
        "runs": sum(by_status.values()),
        "by_status": dict(by_status),
        "by_profile": dict(by_profile),
        "fail_reasons": dict(fail_reasons.most_common(5)),
        "fail_by_profile": {
            p: dict(c.most_common(3)) for p, c in fail_by_profile.items()
        },
    }


def render_markdown(d: dict) -> str:
    if d.get("error"):
        return f"### Kanban AIチーム ({d['date']})\n{d['error']}"
    if d["runs"] == 0:
        return f"### Kanban AIチーム ({d['date']})\n（前日の実行なし）"

    lines = [f"### Kanban AIチーム ({d['date']}) — {d['runs']} run"]
    bs = d["by_status"]
    done = bs.get("completed", 0) + bs.get("done", 0)
    fail = sum(bs.get(s, 0) for s in FAIL_STATUSES)
    lines.append(f"- 完了: {done} / 失敗: {fail}")
    if bs:
        detail = ", ".join(f"{k}={v}" for k, v in sorted(bs.items()))
        lines.append(f"- 内訳: {detail}")
    if d["fail_reasons"]:
        lines.append("- 失敗原因 Top:")
        for k, v in d["fail_reasons"].items():
            lines.append(f"  - {k}: {v}")
    if d["by_profile"]:
        prof = ", ".join(f"{k}={v}" for k, v in d["by_profile"].items())
        lines.append(f"- プロファイル: {prof}")
    return "\n".join(lines)


def main() -> int:
    date_s = _target_date()
    d = collect(date_s)
    if "--json" in sys.argv:
        print(json.dumps(d, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(d))
    return 0


if __name__ == "__main__":
    sys.exit(main())