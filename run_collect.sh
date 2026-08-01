#!/bin/bash
# ════════════════════════════════════════════
# Kensho Collection Runner (Linux/WSL2版)
# ── 各ポイントサイトからデータ収集 ──
#
# 使い方:
#   ./run_collect.sh                      # 全サイト収集
#   ./run_collect.sh --site moppy         # 特定サイトのみ
#   ./run_collect.sh --dry-run            # ドライラン
# ════════════════════════════════════════════

cd "$(dirname "$0")" || exit 1
PROJECT_DIR="$(pwd)"

export HOME=/home/atushi
# Activate kensho virtual environment
source /home/atushi/kensho-venv/bin/activate

echo "═══════════════════════════════════════════"
echo "Kensho Collection"
echo "═══════════════════════════════════════════"
echo ""

exec python -m scraping.collector "$@"
