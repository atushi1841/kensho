#!/usr/bin/env bash
# Kensho Orchestrator Cron — 15分おきに実行
# Hermes cron (no_agent=True) から呼ばれることを想定
set -euo pipefail

PROJECT_DIR="D:/Project2/kensho"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

LOG_FILE="$LOG_DIR/orchestrator_$(date +%Y%m%d_%H%M%S).log"

cd "$PROJECT_DIR"
exec python orchestrator.py >> "$LOG_FILE" 2>&1
