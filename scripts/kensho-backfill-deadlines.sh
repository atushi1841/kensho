#!/bin/bash
# kensho-backfill-deadlines.sh — deadlineバックフィル（critic v61 / t_331542ac Phase A）
#
# 収集cron（kensho-collect-only.sh）が終了した後に実行され、collected.json の
# 空 deadline（特に cpmeikan 全件欠損）をローカル抽出＋年齢凍結で回填する。
# applier の「締切切れSKIP」を発火させ、期限切れ懸賞への無駄アクションを防止。
#
# 安全策:
#   - /tmp/kensho-collect.lock を flock -w で取得（収集実行中なら収集完了まで待機、
#     30分待っても取れなければスキップ＝次の正時に再試行）
#   - collected.json の排他は backfill_deadlines.py 内の COLLECTED_LOCK（applierとのrace回避）
#   - 冪等: 回填済み項目は再処理されない（deadline非空はスキップ）
# crontab: 45 3,9-21 * * * （収集は毎正時起動・所要13〜25分の後の45分）
set -uo pipefail

PROJECT_DIR="/mnt/d/Project2/kensho"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/backfill_deadlines_$(date +%Y%m%d_%H%M%S).log"

LOCK_FILE="/tmp/kensho-collect.lock"
exec 200>"$LOCK_FILE"
if ! flock -w 1800 200; then
  echo "[$(date '+%H:%M:%S')] ⚠️ 収集ロックが30分解放されず → スキップ" >> "$LOG_FILE"
  exit 0
fi

echo "[$(date '+%H:%M:%S')] deadline backfill 開始" >> "$LOG_FILE"
(
  cd "$PROJECT_DIR"
  export HOME=/home/atushi
  export PYTHONPATH="$PROJECT_DIR"
  timeout 600 /home/atushi/kensho-venv/bin/python backfill_deadlines.py
) >> "$LOG_FILE" 2>&1
RC=$?
echo "[$(date '+%H:%M:%S')] backfill exit rc=$RC" >> "$LOG_FILE"

# ログローテ: 直近7日分だけ残す
find "$LOG_DIR" -name 'backfill_deadlines_*.log' -mtime +7 -delete 2>/dev/null
exit $RC
