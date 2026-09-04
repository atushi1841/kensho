#!/usr/bin/env bash
# scripts/kanban_hn_cleanup.sh
#
# kensho-ai-team kanban の Show HN 重複案件を毎日 1 回自動クローズする。
# 内部で scripts/kanban_hn_cleanup.py --apply を実行する。
# 出力(stdout) は hermes cron の no-agent モードでそのまま local deliver される。
#
# 設置先: ~/.hermes/profiles/kensho-sweeps/scripts/kanban_hn_cleanup.sh
#   (hermes cron は script を ~/.hermes/scripts/ 配下から要求するため)
# workdir には kensho リポジトリ (/mnt/d/Project2/kensho) を指定することを想定。
# workdir が無い/不正な環境でも PROJECT_ROOT を env で上書きできる。
set -euo pipefail
PROJECT_ROOT="${HERMES_KENSHO_ROOT:-/mnt/d/Project2/kensho}"
cd "$PROJECT_ROOT"
python3 "$PROJECT_ROOT/scripts/kanban_hn_cleanup.py" --apply
