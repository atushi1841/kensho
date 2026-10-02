#!/usr/bin/env bash
# revenue-health-check-wrapper — revenue-health-check.pyの実行ラッパー
set -u
SCRIPT="/mnt/d/Project2/kensho/scripts/revenue-health-check.py"
LOG_DIR="/mnt/d/Project2/kensho/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/revenue-health-$(date +%Y%m%d-%H%M%S).log"
/home/atushi/kensho-venv/bin/python3 "$SCRIPT" 2>&1 | tee "$LOG"
exit ${PIPESTATUS[0]}
