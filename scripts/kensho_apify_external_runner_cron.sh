#!/usr/bin/env bash
# kensho-apify-external-runner cron 登録スクリプト / ラッパー
# 毎週月曜 4:00 AM に主要 PPE アクターの外部runを自動起動する

set -euo pipefail
PROJECT_DIR="/mnt/d/Project2/kensho"
VENV_PYTHON="/home/atushi/kensho-venv/bin/python3"
SCRIPT_PATH="${PROJECT_DIR}/scripts/apify_ppe_external_runner.py"

if [ -f "${VENV_PYTHON}" ]; then
    PYTHON_BIN="${VENV_PYTHON}"
else
    PYTHON_BIN="python3"
fi

cd "${PROJECT_DIR}"
exec "${PYTHON_BIN}" "${SCRIPT_PATH}" --top 20
