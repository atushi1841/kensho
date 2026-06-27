#!/bin/bash
# ════════════════════════════════════════════
# Kensho Code Workflow Launcher (Linux/WSL2版)
# ── Aider + DeepSeek公式API + pytest ──
#
# 使い方:
#   ./kensho_code.sh                              # インタラクティブ
#   ./kensho_code.sh "バグ直して"                 # 一発指示
#   ./kensho_code.sh --hermes "ここ直して" file.py  # Hermes連携
#   ./kensho_code.sh --mode plan                  # 計画のみ
#   ./kensho_code.sh --mode test                  # テストのみ
# ════════════════════════════════════════════

cd "$(dirname "$0")" || exit 1
PROJECT_DIR="$(pwd)"

# kensho-venv の Python を使用
PYTHON="$HOME/kensho-venv/bin/python"

exec "${PYTHON}" "${PROJECT_DIR}/tools/kensho_code.py" "$@"
