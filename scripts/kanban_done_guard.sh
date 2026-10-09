#!/usr/bin/env bash
# kensho repo 内からの done guard 呼出wrapper（t_974844f8 対応）.
# card body の検証コマンド `bash scripts/kanban_done_guard.py <task_id>` が
# repo 内で解決できるように、実体は profiles/kensho-sweeps の guard を委譲する。
set -euo pipefail
REAL="/home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py"
if [ ! -f "$REAL" ]; then
  echo "guard 実体不在: $REAL" >&2
  exit 127
fi
exec python3 "$REAL" "$@"
