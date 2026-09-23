#!/bin/bash
# Kensho 稼働サマリー GitHub自動同期 cron wrapper
# 使い方: 下記を crontab に追加
#   55 23 * * * /mnt/d/Project2/kensho/scripts/kensho_github_sync.sh >> /mnt/d/Project2/kensho/logs/github_sync_cron.log 2>&1
#
# 設計:
#   - 非対話を強制（GIT_TERMINAL_PROMPT=0）。credential は env ファイル
#     ($HOME/.config/kensho/github-sync.env) or GCM helper から kensho_github_sync.py が解決する
#   - exit code を必ずログに残す（set -e を使わず自前でハンドリング）
set -uo pipefail

REPO=/mnt/d/Project2/kensho
LOG="$REPO/logs/github_sync_cron.log"

cd "$REPO" || exit 1
mkdir -p "$REPO/logs"

export GIT_TERMINAL_PROMPT=0   # 対話プロンプト禁止（cron でハングさせない）
export GCM_INTERACTIVE=never

/usr/bin/env python3 kensho_github_sync.py >> "$LOG" 2>&1
rc=$?

echo "[sync] $(date '+%Y-%m-%d %H:%M:%S%z') wrapper_exit=$rc" >> "$LOG"
exit "$rc"
