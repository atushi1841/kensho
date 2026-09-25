#!/bin/bash
# kanban_crash_stats.sh — 24h の crash / 浪費時間 / 未着手 ready を 1 行 JSON で出力する。
#
# 実体は scripts/kanban_crash_breaker.py stats（判定ロジックと CLI を同居させ pytest から検証可能にする）。
#
# 履歴（2026-09-25 / t_5ecf88bf 実測）: 旧版は `sqlite3` CLI に依存していたが本環境に
# sqlite3 バイナリが無く "sqlite3: command not found" で **無音失敗**（末尾の `rm` が成功するため
# exit 0 になり、cron からは正常に見えた）。さらに参照 DB が
# /home/atushi/.hermes/kanban/kanban.db（存在しない）で board 列も無かった。
# → python3 標準ライブラリのみ + boards/<board>/kanban.db 参照に置き換え。
set -uo pipefail

# readlink -f で symlink を実体解決する（~/.hermes/scripts/ 経由で呼ばれると
# BASH_SOURCE が symlink パスになり、dirname が本体を見失う。2026-09-25 実測）
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
exec python3 "$SCRIPT_DIR/kanban_crash_breaker.py" stats "$@"
