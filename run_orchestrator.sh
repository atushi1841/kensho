#!/bin/bash
# ════════════════════════════════════════════
# Kensho Orchestrator Runner (Linux/WSL2版)
# ── タスク管理・自動化オーケストレーター ──
#
# 使い方:
#   ./run_orchestrator.sh
#   ./run_orchestrator.sh --dry-run
#   ./run_orchestrator.sh --account account_key
# ════════════════════════════════════════════

cd "$(dirname "$0")" || exit 1
PROJECT_DIR="$(pwd)"

export HOME=/home/atushi
# Activate kensho virtual environment
source /home/atushi/kensho-venv/bin/activate

echo "═══════════════════════════════════════════"
echo "Kensho Orchestrator"
echo "═══════════════════════════════════════════"
echo ""

exec python kensho/orchestrator.py "$@"
