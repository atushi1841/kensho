#!/bin/bash
# Kensho 稼働サマリー GitHub自動同期 cron wrapper
# 使い方: 下記を crontab に追加
#   55 23 * * * /mnt/d/Project2/kensho/scripts/kensho_github_sync.sh >> /mnt/d/Project2/kensho/logs/github_sync_cron.log 2>&1
set -euo pipefail

cd /mnt/d/Project2/kensho || exit 1
/usr/bin/env python3 kensho_github_sync.py >> /mnt/d/Project2/kensho/logs/github_sync_cron.log 2>&1
