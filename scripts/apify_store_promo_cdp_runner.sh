#!/usr/bin/env bash
# scripts/apify_store_promo_cdp_runner.sh
#
# Apify Store PPE プロモーション投稿 の実行ラッパー（CDP + SOCKS5 経路）。
#
# 背景:
#   scripts/apify_store_promo.py の post_with_cdp() は SeleniumBase CDP Mode +
#   SOCKS5 プロキシ経由で X に投稿する。しかし実行環境によっては
#   - Chrome/Chromium の CDP エンドポイント (127.0.0.1:9222) に接続できない
#   - SOCKS5 プロキシ (172.26.80.1:108x) に到達できない
#   - ディスプレイがない（headless でも起動不可）
#   という障害が発生する。本ラッパーはそれらを environment で制御し、
#   投稿経路を「Firefox (Playwright)」にフォールバックできるようにする。
#
# 使い方:
#   bash scripts/apify_store_promo_cdp_runner.sh --slot b
#   KENSHO_BROWSER=firefox USE_PROXY=0 bash scripts/apify_store_promo_cdp_runner.sh --slot b
#
# 環境変数:
#   KENSHO_BROWSER  chrome|firefox|patchright  (default: firefox)
#                    chrome = SeleniumBase CDP Mode (元経路)
#                    firefox = Playwright Firefox（X /status/ が 200 で確実）
#   USE_PROXY        1|0  (default: 1)  SOCKS5 プロキシ使用有無
#   DISPLAY          override (default: 自動検出、未検出なら Xvfb 起動)
#   APIFY_PROMO_VENV Python venv パス（省略時: python3）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PY="${APIFY_PROMO_VENV:-python3}"
LOG="${REPO_ROOT}/logs/apify_store_promo_cdp_runner.log"
SLOT="${1:-b}"
shift || true

# 残り引数は apify_store_promo.py に通过（--force 等）
EXTRA_ARGS="$*"

cd "${REPO_ROOT}"

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) START runner slot=${SLOT} extra='${EXTRA_ARGS}' browser=${KENSHO_BROWSER:-firefox} proxy=${USE_PROXY:-1}" >> "${LOG}"

# ── 1. ディスプレイ確保 ──
if [ -z "${DISPLAY:-}" ] && [ "${KENSHO_BROWSER:-firefox}" != "firefox" ]; then
    # CDP/Chrome 経路 only: X ディスプレイが必要な場合 Xvfb 起動
    if command -v Xvfb >/dev/null 2>&1; then
        DISPLAY=":99"
        export DISPLAY
        Xvfb "${DISPLAY}" -screen 0 1366x768x24 >/dev/null 2>&1 &
        XVFB_PID=$!
        echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) INFO Xvfb started pid=${XVFB_PID} display=${DISPLAY}" >> "${LOG}"
        trap "kill ${XVFB_PID} 2>/dev/null || true" EXIT
    else
        echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) WARN Xvfb not found; CDP 経路は失敗する可能性あり" >> "${LOG}"
    fi
fi

# ── 2. 投稿実行 ──
# KENSHO_BROWSER / USE_PROXY は selenium_cdp.py / browser.py の既定と対応。
# Firefox 経路は /status/ permalink への 403 を回避できる（browser.py 参照）。
export KENSHO_BROWSER="${KENSHO_BROWSER:-firefox}"
export USE_PROXY="${USE_PROXY:-1}"

if "${PY}" scripts/apify_store_promo.py --slot "${SLOT}" ${EXTRA_ARGS} >> "${LOG}" 2>&1; then
    EXIT_CODE=0
else
    EXIT_CODE=$?
    # ── 3. フォールバック: Firefox 経路で再試行（Chrome 経路が失敗した場合）──
    if [ "${KENSHO_BROWSER}" != "firefox" ]; then
        echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) INFO primary(${KENSHO_BROWSER}) failed rc=${EXIT_CODE}; fallback to firefox" >> "${LOG}"
        export KENSHO_BROWSER="firefox"
        if "${PY}" scripts/apify_store_promo.py --slot "${SLOT}" ${EXTRA_ARGS} >> "${LOG}" 2>&1; then
            EXIT_CODE=0
        else
            EXIT_CODE=$?
        fi
    fi
fi

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) END runner exit=${EXIT_CODE}" >> "${LOG}"
exit "${EXIT_CODE}"