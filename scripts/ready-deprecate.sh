#!/usr/bin/env bash
# ready-deprecate.sh
#
# 目的: Kanbanボード(kensho-ai-team)でready状態のまま長時間停滞したタスクを自動アーカイブする
#       worker throughput crisis対応(v17-A part 3/3)
#
# 仕様:
#   - デフォルト48時間以上ready停滞 → archive
#   - デフォルトdry-run(--applyで実実行)
#   - --json 一括取得で高速化(show 106回呼び出しを回避)
#   - 出力: 件数、アーカイブ対象ID、サイレント可
#
# 使い方:
#   bash scripts/ready-deprecate.sh                        # デフォルト48h, dry-run
#   bash scripts/ready-deprecate.sh --hours 72              # 72h閾値で dry-run
#   bash scripts/ready-deprecate.sh --apply --hours 48      # 実実行
#   bash scripts/ready-deprecate.sh --board kensho-ai-team --silent
#
# Cron統合予定: 1日1回深夜4時台

set -euo pipefail

BOARD="${BOARD:-kensho-ai-team}"
HOURS=48
APPLY=0
SILENT=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --board) BOARD="$2"; shift 2 ;;
        --hours) HOURS="$2"; shift 2 ;;
        --apply) APPLY=1; shift ;;
        --silent) SILENT=1; shift ;;
        -h|--help)
            grep -E '^#( |$)' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

THRESHOLD_SEC=$((HOURS * 3600))
NOW=$(date +%s)
TMPFILE=$(mktemp /tmp/ready-deprecate.XXXXXX.json)
trap 'rm -f "$TMPFILE"' EXIT

# Kanbanからready一覧をjsonで一括取得
if ! hermes kanban --board "$BOARD" list --status ready --json >"$TMPFILE" 2>/dev/null; then
    echo "ERROR: hermes kanban list failed" >&2
    exit 1
fi

# JSON件数と閾値超過タスクIDを抽出
# python3で安全にパースしてリスト出力する
read TOTAL_READY ARCHIVE_IDS_LIST <<<"$(python3 - "$TMPFILE" "$NOW" "$THRESHOLD_SEC" <<'PY'
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
now = int(sys.argv[2])
threshold = int(sys.argv[3])
total = len(data)
archive_ids = []
for t in data:
    created = int(t.get("created_at") or 0)
    age = now - created if created > 0 else 0
    if age >= threshold:
        archive_ids.append(f"{t['id']}|{age}")
print(total, " ".join(archive_ids))
PY
)"

if [[ -z "$TOTAL_READY" ]]; then TOTAL_READY=0; fi
read -r -a ARCHIVE_ARRAY <<<"$ARCHIVE_IDS_LIST"
COUNT=${#ARCHIVE_ARRAY[@]}

if [[ "$SILENT" -eq 1 && "$COUNT" -eq 0 ]]; then
    echo "[SILENT]"
    exit 0
fi

echo "ready-deprecate: board=$BOARD threshold=${HOURS}h total_ready=$TOTAL_READY deprecate_target=$COUNT"
if [[ "$COUNT" -gt 0 ]]; then
    for entry in "${ARCHIVE_ARRAY[@]}"; do
        tid="${entry%%|*}"
        age="${entry##*|}"
        age_h=$((age / 3600))
        echo "  - $tid (age=${age_h}h)"
    done
fi

if [[ "$APPLY" -ne 1 ]]; then
    echo "DRY-RUN: pass --apply to archive."
    exit 0
fi

# 実実行
FAILED=0
for entry in "${ARCHIVE_ARRAY[@]}"; do
    tid="${entry%%|*}"
    if hermes kanban --board "$BOARD" archive "$tid" >/dev/null 2>&1; then
        echo "  ✓ archived $tid"
    else
        echo "  ✗ archive failed: $tid" >&2
        FAILED=$((FAILED+1))
    fi
done

echo "DONE: archived=$((COUNT-FAILED)) failed=$FAILED"
exit $(( FAILED > 0 ? 1 : 0 ))
