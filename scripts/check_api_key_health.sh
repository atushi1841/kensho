#!/usr/bin/env bash
# 全プロファイルのAPI鍵健全性を応募前に判定する読取専用監視のラッパー。
# usage: bash scripts/check_api_key_health.sh [--dry-run] [--json] [--out <file>]
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# プロジェクトvenv優先、無ければ python3
if [ -x "${REPO_ROOT}/.venv/bin/python" ]; then
    PY="${REPO_ROOT}/.venv/bin/python"
else
    PY="python3"
fi

exec "$PY" "$REPO_ROOT/scripts/api_key_health.py" "$@"
