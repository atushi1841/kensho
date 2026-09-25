#!/bin/bash
# kanban_crash_circuit_breaker.sh — 盤面側クラッシュループ遮断器（no_agent cron 想定）。
#
# 24h 窓で crashed >= 閾値（既定 3）の ready/running カードを `hermes kanban schedule` で park し、
# 1 枚のカードが worker 枠を占有し続ける状態（実測 24h で crashed=250 / 1 枚最大 64 回）を止める。
#
# 安全弁:
#   * DB は read-only で開く（park は hermes CLI 経由）
#   * kill switch: ~/.hermes/kanban/.crash_breaker.disabled があれば何もしない
#   * CRASH_BREAKER_DRY_RUN=1 で判定のみ
#   * running は claim 失効時のみ対象（稼働中 worker を殺さない）
#   * 平常時（park 0 件）は stdout 無音 = no_agent cron で通知を出さない
set -uo pipefail

# readlink -f で symlink を実体解決する（~/.hermes/scripts/ 経由で呼ばれると
# BASH_SOURCE が symlink パスになり、dirname が本体を見失う。2026-09-25 実測）
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
exec python3 "$SCRIPT_DIR/kanban_crash_breaker.py" run "$@"
