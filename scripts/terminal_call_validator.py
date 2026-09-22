#!/usr/bin/env python3
"""terminal_call_validator — 終端呼出(kanban_complete/block)欠落のサーバ側監視バリデータ (t_f3ba57cb).

背景 / 設計 (t_0f7bdf73 設計再定義 2026-09-22):
  t_0f7bdf73 は「worker側の終端呼出強制ラッパー」を worker 編集コードとして実装しようとして
  4回連続 protocol_violation → blocked になった。実装対象がラッパー自身で、worker がそれを
  書く行為自体が「終端ツール未呼出で rc=0 終了」の protocol_violation を発火する自己矛盾のため
  永久ループする。→ 再設計方針:
    (1) 強制は worker 編集コードでなく実行機構側(hermes-agent dispatcher detect_crashed_workers +
        agent/kanban_stop.py nudge)に既に存在する。t_334219b7 で rc=0 clean-exit は保管 violation 検出
        しつつ failure 計上・ブレーカー発動なしで ready へ自動リカバリされる。(worker コード非依存)
    (2) kensho 側は「終端呼出欠落を実行後検出して可視化する純監視」を担う。本スクリプトはその
        サーバ側バリデータで、読み取り専用・行動変更なし(kanban_complete/block を発行しない)。
        常に exit 0(監視失敗も編集中は計上しない)。結果は loop_health / watchdog / regression ledger
        への統合に使う機械可読 JSON。

本バリデータが検出するもの:
  - status='blocked' かつ last_failure_error が protocol violation 起因 = 終端呼出欠落で沈黙ブロック化。
  - task_events kind='protocol_violation' の発生記録から、回収済み(done/archived か破損後再run)
    vs 未回収(pending)を分類。

使い方:
  python3 scripts/terminal_call_validator.py [--db PATH] [--json]
    --json   機械可読 JSON を stdout(既定は人間向け短文)
    --db     ボードDB(既定: kensho-ai-team board DB、ない場合 $HOME/.hermes/kanban.db)
  exit code は常に 0。
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

PROTOCOL_VIOLATION_MARKER = "%protocol violation%"


def resolve_db() -> Path:
    """ボード DB を解決。kensho-ai-team が無ければ既定 board を探す(読み取り専用前提)。"""
    candidates = [
        Path(os.environ.get("KENSHO_BOARD_DB", "")),
        Path("/home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db"),
        Path(os.environ.get("HERMES_KANBAN_DB", "")),
        Path.home() / ".hermes/kanban.db",
    ]
    for c in candidates:
        # 空 env (>> Path("") == Path(".") ) やディレクトリを拾わない:
        # `.` は exists=True のため無言で選ばれ "disk I/O error" になる。
        if not str(c):
            continue
        if c.is_file():
            return c
    # 最後の候補が存在しない場合は HERMES_WSPATH 等は関知しない。存在しない場合の呼出側で
    # OpenError になるが、監視スクリプトとして「DB 未解決」も exit 0 で JSON に残す。
    return candidates[-1] if candidates else Path("/home/atushi/.hermes/kanban.db")


def open_ro(db: Path) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def collect(con: sqlite3.Connection, now: float) -> dict[str, Any]:
    """終端呼出欠落の現状を収集・分類して返す(JSON 化可能な dict)。"""
    # 1) blocked でありながら protocol violation 起因で沈黙化しているタスク
    blocked_pv: list[tuple[str, int]] = []
    for r in con.execute(
        "SELECT id, consecutive_failures FROM tasks "
        "WHERE status='blocked' AND last_failure_error IS NOT NULL "
        "AND last_failure_error LIKE ?",
        (PROTOCOL_VIOLATION_MARKER,),
    ):
        blocked_pv.append((str(r["id"]), int(r["consecutive_failures"] or 0)))

    # 2) protocol_violation イベント全件を直近24h窓で挽き、回収判定する
    cutoff = now - 24 * 3600
    incidents_24h = 0
    unresolved: dict[str, int] = {}
    for r in con.execute(
        "SELECT task_id, created_at FROM task_events "
        "WHERE kind='protocol_violation' AND created_at>=? ORDER BY created_at",
        (cutoff,),
    ):
        tid = str(r["task_id"])
        incidents_24h += 1
        trow = con.execute("SELECT status FROM tasks WHERE id=?", (tid,)).fetchone()
        if trow is not None and str(trow["status"]) in ("done", "archived"):
            # 終端済み → 回収済み
            continue
        later = con.execute(
            "SELECT COUNT(*) c FROM task_runs WHERE task_id=? AND started_at>?",
            (tid, int(r["created_at"])),
        ).fetchone()
        if later and int(later["c"]) > 0:
            # 破損後に再runあり → 自動リカバリで回収済み
            continue
        unresolved[tid] = unresolved.get(tid, 0) + 1

    # 最新の protocol_violation イベント(表面化のため最新1件のみ)
    last_event: dict[str, Any] | None = None
    row = con.execute(
        "SELECT task_id, created_at FROM task_events WHERE kind='protocol_violation' "
        "ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    if row is not None:
        last_event = {"task_id": str(row["task_id"]), "created_at": int(row["created_at"])}

    return {
        "as_of_epoch": int(now),
        "blocked_protocol_violation": [{"task_id": t, "consecutive_failures": f} for t, f in blocked_pv],
        "blocked_pv_count": sum(1 for _ in blocked_pv),
        "incidents_24h": incidents_24h,
        "unrecovered_24h": unresolved,
        "unrecovered_count_24h": sum(unresolved.values()),
        "last_event": last_event,
        # 設計上の規約: 本バリデータは純監視(行動変更なし)なので終端ツールを発行しない。
        # このカウンタは「サーバ側バリデータが worker 誘導ではなく監視のみに徹している」証明。
        "mode": "readonly_monitor",
    }


def _human(data: dict[str, Any]) -> str:
    lines = [
        f"terminal_call_validator: mode={data['mode']}",
        f"  blocked_pv={data['blocked_pv_count']} incidents_24h={data['incidents_24h']} "
        f"unrecovered_24h={data['unrecovered_count_24h']}",
        "  as_of_epoch=%d" % data["as_of_epoch"],
    ]
    for row in data["blocked_protocol_violation"]:
        lines.append("    blocked-pv %s (cf=%d)" % (row["task_id"], row["consecutive_failures"]))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=None, help="kanban board DB path")
    ap.add_argument("--json", action="store_true", help="JSON 出力")
    args = ap.parse_args(argv)

    db = Path(args.db) if args.db else resolve_db()
    now = time.time()
    try:
        con = open_ro(db)
    except sqlite3.Error as e:
        print(json.dumps({"error": f"Cannot open db {db}: {type(e).__name__}: {e}", "mode": "readonly_monitor"}))
        return 0
    try:
        data = collect(con, now)
    except sqlite3.Error as e:
        con.close()
        print(json.dumps({"error": f"collect failed: {type(e).__name__}: {e}", "mode": "readonly_monitor"}))
        return 0
    con.close()
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=1))
    else:
        print(_human(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
