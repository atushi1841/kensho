#!/usr/bin/env bash
# kensho-ready-watchdog.sh
#
# 目的: Kanbanボード(kensho-ai-team)のreadyタスク停滞を3段階で警告/処分
#       worker throughput crisis対応(v19-B / v22-A)
#       cron-watchdog.sh の構造をVERBATIM再利用(grepカウント+SILENT)
#
# 仕様:
#   - 24h停滞 → comment '[warn] ready 24h'
#   - 72h停滞 → comment '[escalate] ready 72h'
#   - 168h停滞 → archive(deleteより可逆、list --archivedで復旧可)
#   - APPLY=1/SILENT=1がデフォルト(cron --no-agent前提)
#   - 手動実行は --dry-run でコメント投稿を抑制
#
# 使い方:
#   bash scripts/kensho-ready-watchdog.sh --dry-run              # 手動: 対象表示のみ
#   bash scripts/kensho-ready-watchdog.sh --apply                # 実実行
#   bash scripts/kensho-ready-watchdog.sh --hours 12 --dry-run   # 閾値12hで確認
#
# Cron統合: job 8d22d346627b (daily 09:00, --no-agent)

set -euo pipefail

BOARD="kensho-ai-team"
HOURS_WARN=24
HOURS_ESCALATE=72
HOURS_DELETE=168
APPLY="${APPLY:-1}"   # cron(--no-agent)は実実行前提。手動は--dry-runで上書き
SILENT="${SILENT:-1}" # 問題0件時は空stdout=サイレント(--no-agent規約)

while [[ $# -gt 0 ]]; do
    case "$1" in
        --board) BOARD="$2"; shift 2 ;;
        --hours) HOURS_WARN="$2"; HOURS_ESCALATE=$((HOURS_WARN*3)) HOURS_DELETE=$((HOURS_WARN*7)); shift 2 ;;
        --apply) APPLY=1; shift ;;
        --dry-run) APPLY=0; shift ;;
        --silent) SILENT=1; shift ;;
        -h|--help)
            grep -E '^#( |$)' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

TMPFILE=$(mktemp /tmp/ready-watchdog.XXXXXX.json)
trap 'rm -f "$TMPFILE"' EXIT

# Kanbanからready一覧をjsonで一括取得(180s→2.5s高速化)
if ! hermes kanban --board "$BOARD" list --status ready --json >"$TMPFILE" 2>/dev/null; then
    echo "ERROR: hermes kanban list failed" >&2
    exit 1
fi

# 閾値別にwarn/escalate/delete対象を抽出(python3で安全パース)
WARN_TGT=()
ESC_TGT=()
DEL_TGT=()
python3 - "$TMPFILE" "$HOURS_WARN" "$HOURS_ESCALATE" "$HOURS_DELETE" <<'PY' >/tmp/ready-watchdog-parse.txt
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
warn_h, esc_h, del_h = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
import time
now = int(time.time())
for t in data:
    created = int(t.get("created_at") or 0)
    if created <= 0:
        continue
    age_h = (now - created) // 3600
    tid = t["id"]
    if age_h >= del_h:
        print(f"DEL\t{tid}")
    elif age_h >= esc_h:
        print(f"ESC\t{tid}")
    elif age_h >= warn_h:
        print(f"WARN\t{tid}")
PY

WARN_TGT=(); ESC_TGT=(); DEL_TGT=()
while IFS=$'\t' read -r level tid; do
    case "$level" in
        WARN) WARN_TGT+=("$tid") ;;
        ESC)  ESC_TGT+=("$tid") ;;
        DEL)  DEL_TGT+=("$tid") ;;
    esac
done < /tmp/ready-watchdog-parse.txt
rm -f /tmp/ready-watchdog-parse.txt

# t_848e1beb: protocol_violation（終端kanban呼出なしでrc=0抜け）でblockedに落ちた
# workerタスクを検出して報告。dispatcherが失敗扱いするが、そのまま放置・無自覚だと
# 手動復旧待ちになるため、ここで可視化する（contributor: user 2026-09-22）。
PROTO_TGT=()
PROTO_DB="/home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db"
if [ -f "$PROTO_DB" ]; then
    python3 - "$PROTO_DB" <<'PY' >/tmp/ready-watchdog-proto.txt 2>/dev/null
import sqlite3, sys
try:
    c = sqlite3.connect(sys.argv[1])
    rows = c.execute(
        "select id, title, assignee from tasks "
        "where status='blocked' and last_failure_error like '%protocol violation%' "
        "order by created_at desc limit 10").fetchall()
    for r in rows:
        print(f"{r[0]}\t{r[2]}\t{r[1]}")
except Exception:
    pass
PY
    while IFS=$'\t' read -r ptid pag ptitle; do
        [ -n "$ptid" ] && PROTO_TGT+=("$ptid:: $ptitle (assignee=$pag)")
    done < /tmp/ready-watchdog-proto.txt
    rm -f /tmp/ready-watchdog-proto.txt
fi

TOTAL=$(( ${#WARN_TGT[@]} + ${#ESC_TGT[@]} + ${#DEL_TGT[@]} + ${#PROTO_TGT[@]} ))

if [[ "$SILENT" -eq 1 && "$TOTAL" -eq 0 ]]; then
    # --no-agentモード: 空stdoutでサイレント配信抑制
    exit 0
fi

echo "kensho-ready-watchdog: board=$BOARD warn_h=${HOURS_WARN} esc_h=${HOURS_ESCALATE} del_h=${HOURS_DELETE}"
echo "  WARN(>=${HOURS_WARN}h): ${#WARN_TGT[@]}件"
echo "  ESCALATE(>=${HOURS_ESCALATE}h): ${#ESC_TGT[@]}件"
echo "  DELETE(>=${HOURS_DELETE}h): ${#DEL_TGT[@]}件"
echo "  PROTO_VIOLATION_BLOCKED: ${#PROTO_TGT[@]}件"

if [[ ${#WARN_TGT[@]} -gt 0 ]]; then
    printf '  ⚠️  '; printf '%s ' "${WARN_TGT[@]}"; echo
fi
if [[ ${#ESC_TGT[@]} -gt 0 ]]; then
    printf '  🔴 '; printf '%s ' "${ESC_TGT[@]}"; echo
fi
if [[ ${#DEL_TGT[@]} -gt 0 ]]; then
    printf '  💀 '; printf '%s ' "${DEL_TGT[@]}"; echo
fi
if [[ ${#PROTO_TGT[@]} -gt 0 ]]; then
    printf '  🚨 protocol_violation blocked: '
    printf '%s | ' "${PROTO_TGT[@]}"; echo
fi

if [[ "$APPLY" -ne 1 ]]; then
    echo "DRY-RUN: pass --apply to comment/delete."
    exit 0
fi

# 実実行: warn/escalateはコメント、deleteはarchive(可逆)
FAILED=0
for tid in "${WARN_TGT[@]}"; do
    if hermes kanban --board "$BOARD" comment "$tid" "[warn] ready ${HOURS_WARN}h 経過。worker着手を要請" >/dev/null 2>&1; then
        echo "  ✓ warned $tid"
    else
        echo "  ✗ warn failed: $tid" >&2
        FAILED=$((FAILED+1))
    fi
done

for tid in "${ESC_TGT[@]}"; do
    if hermes kanban --board "$BOARD" comment "$tid" "[escalate] ready ${HOURS_ESCALATE}h 経過。critic再投入または要ユーザー対応" >/dev/null 2>&1; then
        echo "  ✓ escalated $tid"
    else
        echo "  ✗ escalate failed: $tid" >&2
        FAILED=$((FAILED+1))
    fi
done

for tid in "${DEL_TGT[@]}"; do
    # archiveを優先(deleteより可逆性高)
    if hermes kanban --board "$BOARD" archive "$tid" >/dev/null 2>&1; then
        echo "  ✓ archived $tid (delete閾値 ${HOURS_DELETE}h超)"
    else
        echo "  ✗ archive failed: $tid" >&2
        FAILED=$((FAILED+1))
    fi
done

echo "DONE: warned=${#WARN_TGT[@]} escalated=${#ESC_TGT[@]} archived=${#DEL_TGT[@]} failed=$FAILED"
exit $(( FAILED > 0 ? 1 : 0 ))
