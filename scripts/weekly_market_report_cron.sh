#!/bin/bash
# weekly_market_report_cron.sh — 週次マーケットレポート自動生成
# 日時: 毎週月曜 6:00 (JST)
# 用途: t_1b2ecfa1 週次マーケットレポート有料購読

set -euo pipefail

PROFILE_DIR="/home/atushi/.hermes/profiles/kensho-sweeps"
PROJECT_DIR="/mnt/d/Project2/kensho"
LOG_DIR="$PROJECT_DIR/logs"
RUN_LOG="$LOG_DIR/weekly_market_report_cron_$(date +%Y%m%d).log"

mkdir -p "$LOG_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] weekly_market_report cron start" >> "$RUN_LOG"

# 実行
cd "$PROJECT_DIR"
source .env 2>/dev/null
python3 reports/weekly_market_report.py >> "$RUN_LOG" 2>&1

EXIT_CODE=$?
echo "[$(date '+%Y-%m-%d %H:%M:%S')] weekly_market_report cron exit=$EXIT_CODE" >> "$RUN_LOG"

exit $EXIT_CODE