#!/bin/bash
# ════════════════════════════════════════════
# Kensho Apply Runner (Linux/WSL2版)
# ── 特定アカウントの自動応募 ──
#
# 使い方:
#   ./run_apply.sh <account_key>
#   例: ./run_apply.sh moppy_user1
# ════════════════════════════════════════════

cd "$(dirname "$0")" || exit 1
PROJECT_DIR="$(pwd)"

export HOME=/home/atushi
# Activate kensho virtual environment
source /home/atushi/kensho-venv/bin/activate

ACCOUNT_KEY="${1:-}"
if [[ -z "${ACCOUNT_KEY}" ]]; then
    echo "❌ 使用方法: $0 <account_key>"
    echo "   例: $0 moppy_user1"
    exit 1
fi

echo "═══════════════════════════════════════════"
echo "Kensho Apply — Account: ${ACCOUNT_KEY}"
echo "═══════════════════════════════════════════"
echo ""

shift
exec python -m application.applier "${ACCOUNT_KEY}" "$@"
