#!/bin/bash
# ════════════════════════════════════════════
# Aider Launcher for Kensho (Linux/WSL2版)
# ── DeepSeek / OpenRouter 自動判定 ──
#
# 使い方:
#   ./aider_kensho.sh                    — インタラクティブモード
#   ./aider_kensho.sh "バグを直して"     — 1回だけ実行
#   ./aider_kensho.sh --architect        — 計画→実行モード
# ════════════════════════════════════════════

cd "$(dirname "$0")" || exit 1
PROJECT_DIR="$(pwd)"

# kensho-venv の Python を使用
PYTHON="$HOME/kensho-venv/bin/python"

# Python経由のランチャーを使う（APIキーの特殊文字対策）
exec "${PYTHON}" "${PROJECT_DIR}/tools/aider_launcher.py" "$@"
