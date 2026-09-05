#!/usr/bin/env bash
# scripts/gumroad_x_post.sh — v21-C Gumroad agyhq X 日次自動投稿ラッパー
#
# kanban_hn_cleanup.sh と同じ「profile 配下 .sh + 定期実行」パターン。
# 内部で scripts/gumroad_x_post.py を実行する（ウィンドウ・日次dedupはpy側が実施）。
# 対象ウィンドウ (9/5〜9/11) 外・投稿済み日は py が安全スキップするため、
# 毎日実行しても冪等。
#
# 設置先: ~/.hermes/profiles/kensho-revenue-worker/scripts/gumroad_x_post.sh
#   + native crontab から毎日実行（kensho-apify-seo-effect-sched.sh と同型）。
# 前提: .venv に curl_cffi が必要（system python3 には無いため venv python で実行）。
set -uo pipefail

PROJECT_ROOT="${HERMES_KENSHO_ROOT:-/mnt/d/Project2/kensho}"
PY="${PROJECT_ROOT}/.venv/bin/python"
[ -x "$PY" ] || PY="python3"

for _i in $(seq 1 30); do
  [ -d /mnt/d/Project2 ] && break
  sleep 10
done
[ -d /mnt/d/Project2 ] || { echo "D:ドライブ未マウント"; exit 1; }

cd "$PROJECT_ROOT"
"$PY" "$PROJECT_ROOT/scripts/gumroad_x_post.py" 2>&1
