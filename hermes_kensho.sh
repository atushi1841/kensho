#!/bin/bash
# ════════════════════════════════════════════
# Kensho Hermes Launcher (Linux/WSL2版)
# ── 事前チェック → Hermes起動 ──
#
# 使い方:
#   ./hermes_kensho.sh                    — 事前チェック後にhermes起動
#   ./hermes_kensho.sh --check-only      — チェックのみ（hermes起動しない）
#   ./hermes_kensho.sh --force-reset     — 強制初期化後にhermes起動
#   ./hermes_kensho.sh --skip-check      — チェックせず直接hermes起動
# ════════════════════════════════════════════

set -euo pipefail

PROJECT_DIR="/mnt/d/Project2/kensho"
PYTHON="$HOME/kensho-venv/bin/python"
HERMES="$HOME/kensho-venv/bin/hermes"

CHECK_ONLY=0
FORCE_RESET=0
SKIP_CHECK=0

# Parse arguments
ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --check-only)  CHECK_ONLY=1; shift ;;
        --force-reset) FORCE_RESET=1; shift ;;
        --skip-check)  SKIP_CHECK=1; shift ;;
        *) ARGS+=("$1"); shift ;;
    esac
done
set -- "${ARGS[@]}"

echo "═══════════════════════════════════════════"
echo "Kensho Hermes Launcher"
echo "═══════════════════════════════════════════"
echo ""
echo "Project: ${PROJECT_DIR}"
echo "Python:  ${PYTHON}"
echo "Hermes:  ${HERMES}"
echo ""

if [[ ${SKIP_CHECK} -eq 1 ]]; then
    echo "[SKIP] 事前チェックをスキップ"
    goto_launch=true
else
    # ── Step 1: Health Check ──
    echo "[1/2] Running Health Check..."
    if [[ ${FORCE_RESET} -eq 1 ]]; then
        "${PYTHON}" "${PROJECT_DIR}/tools/health_check.py" --force-reset || true
    else
        "${PYTHON}" "${PROJECT_DIR}/tools/health_check.py" || true
    fi
    HC_EXIT=$?

    if [[ ${HC_EXIT} -ne 0 ]]; then
        echo "⚠ Health Check で警告があります — 続行しますか？"
        read -r -p "続行(y) / 中止(N): " yn
        case "$yn" in
            [yY]*) ;;
            *) echo "中止しました"; exit 1 ;;
        esac
    fi

    # ── Step 2: Hindsight Guard ──
    echo "[2/2] Running Hindsight Guard..."
    if [[ ${FORCE_RESET} -eq 1 ]]; then
        "${PYTHON}" "${PROJECT_DIR}/tools/hindsight_guard.py" --force-reset || true
    else
        "${PYTHON}" "${PROJECT_DIR}/tools/hindsight_guard.py" || true
    fi
    HG_EXIT=$?

    if [[ ${HG_EXIT} -ge 2 ]]; then
        echo "❌ Hindsight Guard で修復不能なエラー — 手動対応が必要です"
        echo "    ログ: ${PROJECT_DIR}/logs/hindsight_guard.log"
        exit 2
    fi

    if [[ ${CHECK_ONLY} -eq 1 ]]; then
        echo ""
        echo "✅ チェック完了（--check-only のため終了）"
        exit 0
    fi

    echo ""
    echo "✅ 事前チェック完了 — Hermes を起動します..."
    echo ""
fi

# ── Hindsight起動時のログをクリア（巨大化防止）──
HINDSIGHT_LOG="$HOME/.hindsight/profiles/hermes.log"
if [[ -f "${HINDSIGHT_LOG}" ]]; then
    LOG_SIZE=$(stat -c%s "${HINDSIGHT_LOG}" 2>/dev/null || echo 0)
    if [[ ${LOG_SIZE} -gt 10485760 ]]; then
        rm -f "${HINDSIGHT_LOG}"
        echo "[CLEANUP] hindsight.log が10MB超のため削除"
    fi
fi

# ── ロックファイル削除 ──
LOCK_FILE="$HOME/.hindsight/profiles/hermes.lock"
if [[ -f "${LOCK_FILE}" ]]; then
    rm -f "${LOCK_FILE}"
fi

# ── Hermes起動（kensho-sweeps profile） ──
echo "🚀 Launching Hermes (kensho-sweeps profile)..."
echo ""
"${HERMES}" --profile kensho-sweeps "$@"
EXIT_CODE=$?

if [[ ${EXIT_CODE} -ne 0 ]]; then
    echo "❌ Hermes が異常終了しました (exit code ${EXIT_CODE})"
    exit ${EXIT_CODE}
fi

exit 0
