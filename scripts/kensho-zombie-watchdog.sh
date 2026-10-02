#!/usr/bin/env bash
# kensho-zombie-watchdog.sh — ゾンビタスク自動検出・自動unblock+再割り当て (kanban t_7748d284)
#
# 目的: worker が作業を完了しても kanban_complete/kanban_block を呼び忘れたまま
#       rc=0 で抜け、プロトコル違反カウンタで回路遮断された「blocked で永久滞留」の
#       タスク（ゾンビ）を検出して自動 unblock（blocked→ready）し、dispatcher に
#       再割り当てさせる。~96% のケースは再試行で完了できる（done_guard 教訓、t_7748d284）。
#
# 検知シグネチャ（ゾンビ = worker 正常終了でも終端kanban呼び出し無しで遮断）:
#   タスクが status='blocked' かつ 直近の遮断原因が clean-exit プロトコル違反:
#     - last_failure_error LIKE '%protocol violation%'
#     - または 最新の閉じた run が outcome IN ('crashed') かつ
#       json_extract(metadata,'$.protocol_violation') = 1 で、その後 completed が無い
#   上記タスクは「成果は出ていて端末処理を忘れた」候補。unblock → ready → 再割当。
#
# ループガード（block→unblock→block churn 防止）:
#   - 台帳 state/{zombie_ledger.json} に task_id → {unblocks, last_ts} を記録。
#     同一タスクの自動 unblock は ZOMBIE_MAX_UNBLOCKS(既定2)回まで。
#     超えたら unblock せず escalation として残す（critic/人間へ）。
#   - 台帳の unblocks は complete したら 0 に戻す（成功でリセット）。
#
# 使い方:
#   bash scripts/kensho-zombie-watchdog.sh --dry-run           # 手動: 対象表示のみ
#   bash scripts/kensho-zombie-watchdog.sh --apply             # 実効: unblock+再割当
#   APPLY=0 bash scripts/kensho-zombie-watchdog.sh             # 環境変数でも dry-run
#
# Cron統合: APPLY=1 既定。検出0件時は空stdout=サイレント(--no-agent規約)。
#   登録例: hermes cron ... script='kensho-zombie-watchdog.sh' schedule='*/30 * * * *'

set -euo pipefail

BOARD="${KENSHO_ZOMBIE_BOARD:-kensho-ai-team}"
APPLY="${APPLY:-1}"          # 既定apply（cronは引数を渡せない→既定実効）
SILENT="${SILENT:-1}"
MAX_UNBLOCKS="${ZOMBIE_MAX_UNBLOCKS:-2}"    # 同一タスク自動unblockの上限
STATE_DIR="${KENSHO_ZOMBIE_STATE_DIR:-/home/atushi/.hermes/profiles/kensho-sweeps/scripts/state}"
LEDGER="${STATE_DIR}/zombie_ledger.json"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --board) BOARD="$2"; shift 2 ;;
        --apply) APPLY=1; shift ;;
        --dry-run) APPLY=0; shift ;;
        --silent) SILENT=1; shift ;;
        --max-unblocks) MAX_UNBLOCKS="$2"; shift 2 ;;
        -h|--help)
            grep -E '^#( |$)' "$0" | sed 's/^# \?//'
            exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

# hermes venv python を解決（hermes_cli import 用）
# 注意: hermes_cli は hermes-agent ディレクトリ配下のモジュール（utils.py 等）を
# sys.path 経由で import する。PYTHONPATH を通さないと
# ModuleNotFoundError: No module named 'hermes_yaml' で落ちる（2026-10-01 実測）
HERMES_AGENT_DIR="${HERMES_AGENT_DIR:-$HOME/.hermes/hermes-agent}"
PY="python3"
if ! python3 -c 'import hermes_cli.kanban_db' >/dev/null 2>&1; then
    VENV="$HERMES_AGENT_DIR/venv/bin/python3"
    [ -x "$VENV" ] && PY="$VENV"
fi
export PYTHONPATH="$HERMES_AGENT_DIR${PYTHONPATH:+:$PYTHONPATH}"

mkdir -p "$STATE_DIR" 2>/dev/null || true

"$PY" - "$BOARD" "$MAX_UNBLOCKS" "$APPLY" "$SILENT" "$LEDGER" <<'PYEOF'
import json
import os
import sqlite3
import sys
import time

from contextlib import closing

board = sys.argv[1]
max_unblocks = int(sys.argv[2])
apply_mode = int(sys.argv[3])
silent = int(sys.argv[4])
ledger_path = sys.argv[5]
now = int(time.time())

import hermes_cli.kanban_db as kb

# 台帳読込: task_id -> {"unblocks": int, "last_ts": int, "last_unblocked_at": int}
ledger = {}
if os.path.exists(ledger_path):
    try:
        ledger = json.loads(open(ledger_path, encoding="utf-8").read()) or {}
    except Exception:
        ledger = {}

def _is_blocked_by_pv(conn, task_id: str) -> bool:
    """blocked タスクの遮断原因が clean-exit プロトコル違反か判定する。"""
    row = conn.execute(
        "SELECT last_failure_error FROM tasks WHERE id = ?", (task_id,)
    ).fetchone()
    if row and row["last_failure_error"] and "protocol violation" in row["last_failure_error"]:
        return True
    # 直近の閉じた run が protocol_violation の crashed で、かつその後 completed が無い
    last = conn.execute(
        "SELECT id, outcome, metadata, ended_at FROM task_runs "
        "WHERE task_id = ? AND ended_at IS NOT NULL ORDER BY id DESC LIMIT 1",
        (task_id,),
    ).fetchone()
    if last and last["outcome"] == "crashed" and last["metadata"]:
        try:
            if json.loads(last["metadata"]).get("protocol_violation"):
                # ensure no completed run after the crashed one
                after = conn.execute(
                    "SELECT 1 FROM task_runs WHERE task_id = ? "
                    "AND outcome = 'completed' AND ended_at > ? LIMIT 1",
                    (task_id, last["ended_at"]),
                ).fetchone()
                return after is None
        except (ValueError, TypeError):
            pass
    return False

targets = []
with closing(sqlite3.connect(kb.kanban_db_path(board))) as conn:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, title, assignee, created_at FROM tasks WHERE status = 'blocked'"
    ).fetchall()
    for r in rows:
        tid = r["id"]
        if not _is_blocked_by_pv(conn, tid):
            continue
        ent = ledger.get(tid, {})
        unblocks = int(ent.get("unblocks", 0))
        targets.append({
            "id": tid,
            "title": (r["title"] or "")[:60],
            "assignee": r["assignee"] or "",
            "unblocks": unblocks,
            "age_h": (now - int(r["created_at"])) // 3600,
        })

# 上限超過（escalation依存）と自動unblock対象を分ける
escalate = [t for t in targets if t["unblocks"] >= max_unblocks]
auto_ok = [t for t in targets if t["unblocks"] < max_unblocks]

unblocked, failed = [], []
if apply_mode and auto_ok:
    with closing(sqlite3.connect(kb.kanban_db_path(board))) as conn:
        conn.row_factory = sqlite3.Row
        for t in auto_ok:
            tid = t["id"]
            try:
                kb.add_comment(
                    conn, tid, author="kensho-sweeps",
                    body="[zombie-watchdog] clean-exitプロトコル違反でblocked滞留を検出。"
                         "自動 unblock→再割当します (t_7748d284)。",
                )
            except Exception:
                pass  # comment failureは致命的でない
        for t in auto_ok:
            tid = t["id"]
            try:
                ok = kb.unblock_task(conn, tid)
                (unblocked if ok else failed).append(tid)
            except Exception as e:  # noqa: BLE001
                failed.append(f"{tid}({type(e).__name__})")
    # 台帳更新（unblock成功分のみ）
    if unblocked:
        for tid in unblocked:
            ent = ledger.setdefault(tid, {"unblocks": 0, "last_ts": 0})
            ent["unblocks"] = int(ent.get("unblocks", 0)) + 1
            ent["last_ts"] = now
        os.makedirs(os.path.dirname(ledger_path), exist_ok=True)
        with open(ledger_path, "w", encoding="utf-8") as f:
            json.dump(ledger, f, ensure_ascii=False, indent=2)

lines = []
total = len(targets)
if apply_mode:
    if total == 0 and silent:
        sys.exit(0)
    lines.append(
        f"zombie-watchdog: board={board} max_unblocks={max_unblocks} "
        f"detected={total} auto_unblocked={len(unblocked)} failed={len(failed)} "
        f"escalated={len(escalate)}"
    )
    for t in targets:
        mark = "OK" if t["id"] in unblocked else ("ESC" if t["id"] in escalate else "FAIL")
        lines.append(
            f"  [{mark}] {t['id']} unblocks={t['unblocks']} age={t['age_h']}h "
            f"assignee={t['assignee']} :: {t['title']}"
        )
    if escalate:
        lines.append(
            "  自動unblock上限超過: critic/人間による判断が必要 "
            "(hermes kanban show で確認)"
        )
else:
    header = (
        f"zombie-watchdog: board={board} max_unblocks={max_unblocks} "
        f"zombie={total} (escalate={len(escalate)})"
    )
    lines.append(header)
    for t in targets:
        lines.append(
            f"  {t['id']} unblocks={t['unblocks']} age={t['age_h']}h "
            f"assignee={t['assignee']} :: {t['title']}"
        )
    if total == 0 and silent:
        sys.exit(0)
    if total == 0:
        lines.append("  (none — no blocked-by-protocol-violation zombie tasks)")
    else:
        lines.append("DRY-RUN: pass --apply to unblock+reassign (blocked->ready)")

for ln in lines:
    print(ln)
PYEOF
