#!/usr/bin/env bash
# kensho-goal-stuck-watchdog.sh
#
# 目的: goal_mode カードが ready/running のまま N 時間「無変化」を検知して可視化する。
#       t_fa046d3a: goal judge が BadRequestError を返し続け、実装・検証・push は完了済み
#       なのに 34.5h も ready/running に滞留した（判定期限が働かなかった再発監視）。
#
# 構造は scripts/kensho-ready-watchdog.sh と同じ（--no-agent cron 規約）:
#   - 問題0件は空 stdout でサイレント
#   - --dry-run で対象表示のみ（手動確認）、--apply で comment 投稿
#   - 24h=warn / 72h=escalate の2段階
#
# 「無変化」= max(created_at, last_heartbeat_at, updated_at) からの経過時間。
# board スキーマの列有無に依存しないよう PRAGMA で列を発見して使う。
#
# 使い方:
#   bash scripts/kensho-goal-stuck-watchdog.sh --dry-run
#   bash scripts/kensho-goal-stuck-watchdog.sh --apply
#
# Cron統合: crontab に 30分おき --apply（応募停止検知 cron と同構造）

set -euo pipefail

BOARD="kensho-ai-team"
DB="/home/atushi/.hermes/kanban/boards/${BOARD}/kanban.db"
HOURS_WARN=24
HOURS_ESCALATE=72
APPLY="${APPLY:-1}"
SILENT="${SILENT:-1}"

HERMES_VENV_BIN="${HERMES_VENV_BIN:-/home/atushi/.hermes/hermes-agent/venv/bin}"
HERMES_BIN="${HERMES_VENV_BIN}/hermes"
if [ ! -x "$HERMES_BIN" ]; then
    HERMES_BIN="$(command -v hermes || true)"
fi
if [ -z "${HERMES_BIN:-}" ]; then
    echo "kensho-goal-stuck-watchdog: ERROR: hermes CLI not found" >&2
    exit 127
fi

while [[ $# -gt 0 ]]; do
    case "$1" in
        --hours) HOURS_WARN="$2"; HOURS_ESCALATE=$((HOURS_WARN*3)); shift 2 ;;
        --apply) APPLY=1; shift ;;
        --dry-run) APPLY=0; shift ;;
        --board) BOARD="$2"; DB="/home/atushi/.hermes/kanban/boards/${BOARD}/kanban.db"; shift 2 ;;
        -h|--help) grep -E '^#( |$)' "$0" | sed 's/^# \?//'; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

[ -f "$DB" ] || { echo "ERROR: board db not found: $DB" >&2; exit 1; }

REPORT="$(mktemp /tmp/goal-stuck.XXXXXX.txt)"
trap 'rm -f "$REPORT" "$REPORT".apply 2>/dev/null' EXIT

python3 - "$DB" "$HOURS_WARN" "$HOURS_ESCALATE" >"$REPORT" <<'PY'
import sqlite3, sys, time

db, warn_h, esc_h = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
conn = sqlite3.connect(db)
cols = {r[1] for r in conn.execute("PRAGMA table_info(tasks)")}
if "goal_mode" not in cols:
    sys.exit(0)  # board without goal_mode support — nothing to watch

# Last-activity column candidates, most meaningful first.
cands = [c for c in ("last_heartbeat_at", "updated_at", "last_activity_at", "created_at") if c in cols]
expr = "COALESCE(MAX(%s), 0)" % ", ".join(cands) if len(cands) > 1 else cands[0]

now = int(time.time())
rows = conn.execute(
    f"SELECT id, status, title, {expr} AS last_seen "
    f"FROM tasks WHERE goal_mode = 1 AND status IN ('ready', 'running')"
).fetchall()

hits = []
for tid, status, title, last_seen in rows:
    last_seen = int(last_seen or 0)
    if last_seen <= 0:
        last_seen = int(conn.execute(
            "SELECT COALESCE(created_at,0) FROM tasks WHERE id=?", (tid,)).fetchone()[0] or 0)
    age_h = (now - last_seen) // 3600 if last_seen else -1
    if age_h < 0:
        continue
    level = "ESC" if age_h >= esc_h else ("WARN" if age_h >= warn_h else None)
    if level:
        hits.append((level, age_h, tid, status, (title or "")[:70]))

for level, age_h, tid, status, title in sorted(hits, key=lambda h: -h[1]):
    print(f"{level}\t{age_h}\t{tid}\t{status}\t{title}")
PY

TOTAL=$(grep -c . "$REPORT" 2>/dev/null || true)
if [ "$SILENT" = 1 ] && [ "${TOTAL:-0}" -eq 0 ]; then
    exit 0   # --no-agent: 空 stdout でサイレント
fi

echo "kensho-goal-stuck-watchdog: board=$BOARD warn_h=$HOURS_WARN esc_h=$HOURS_ESCALATE goal_mode-only"
if [ "${TOTAL:-0}" -eq 0 ]; then
    echo "  goal_mode 滞留: 0件"
else
    printf '  '; printf '%s | ' "$(tr '\t' ' ' < "$REPORT")"; echo
fi

if [ "$APPLY" -ne 1 ]; then
    echo "DRY-RUN: pass --apply to comment."
    exit 0
fi

FAILED=0
while IFS=$'\t' read -r level age_h tid status title; do
    [ -n "$tid" ] || continue
    if [ "$level" = "ESC" ]; then
        MSG="[escalate] goal_mode が ${age_h}h ready/running のまま無変化 (status=${status})。judge 失敗による完成判定不能を疑い、auxiliary.goal_judge の provider/model を確認のうえ人間判断で done/blocked へ。title: ${title}"
    else
        MSG="[warn] goal_mode が ${age_h}h ready/running のまま無変化 (status=${status})。進捗・judge 状態を確認。title: ${title}"
    fi
    if "$HERMES_BIN" kanban --board "$BOARD" comment "$tid" "$MSG" >/dev/null 2>&1; then
        echo "  ✓ $level $tid (${age_h}h)"
    else
        echo "  ✗ comment failed: $tid" >&2
        FAILED=$((FAILED+1))
    fi
done < "$REPORT"

echo "DONE: stale=${TOTAL:-0} failed=$FAILED"
exit $(( FAILED > 0 ? 1 : 0 ))
