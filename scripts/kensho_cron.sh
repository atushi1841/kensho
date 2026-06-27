#!/usr/bin/env bash
# Kensho Orchestrator Cron — 15分おきに実行
# Linux cron / WSL2 から呼ばれることを想定
set -euo pipefail

PROJECT_DIR="/mnt/d/Project2/kensho"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

LOG_FILE="$LOG_DIR/orchestrator_$(date +%Y%m%d_%H%M%S).log"

cd "$PROJECT_DIR"
source "$HOME/kensho-venv/bin/activate"
exec python orchestrator.py >> "$LOG_FILE" 2>&1
