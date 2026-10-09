#!/usr/bin/env bash
# reddit_warmup_cron.sh — Reddit 温めコメントの自動投稿（cron用）
#
# 設計上の約束:
#   - 1回の実行で投稿するのは最大1件（エージェント側の max_per_run=1）
#   - 休み日は計画ごと次の活動日へ繰り越し、当日は投稿しない
#   - 予定時刻より先の分は撃たない（前倒し投稿を防ぐ）
#   - 403 が出たら warmup_stop.flag を立てて停止（BOTシグナルを増幅させない）
#   - go.flag が無い場合は何もせず終了する（ユーザーが設置したことを確認済みの印）
#
# go.flag を置く = その回線で動かしてよい、という意思表示（既存ジョブと同じ思想）。
# go.flag の24h TTLは廃止。ユーザーが設置した時点のegress検証で継続する。
set -uo pipefail

REPO=/mnt/d/Project2/kensho
LOG="$REPO/logs/reddit_warmup.log"
GO_FLAG="$REPO/data/reddit/go.flag"
STOP_FLAG="$REPO/data/reddit/warmup_stop.flag"

mkdir -p "$REPO/logs"
echo "=== $(date '+%F %T') start ===" >>"$LOG"

cd "$REPO" || exit 1

# 停止フラグが立っていたら触らない（403の再試行でシグナルを増やさない）
if [ -f "$STOP_FLAG" ]; then
  echo "$(date '+%F %T') SKIP: stop flag present ($(cat "$STOP_FLAG" 2>/dev/null))" >>"$LOG"
  exit 0
fi

# 回線ゲート: go.flag が必要（TTLなし・ユーザー設置が継続の証）
if [ ! -f "$GO_FLAG" ]; then
  echo "$(date '+%F %T') SKIP: go.flag not present - 回線を切り替えたら作成してください" >>"$LOG"
  exit 0
fi

source /home/atushi/kensho-venv/bin/activate 2>/dev/null
out=$(python3 scripts/reddit_warmup_agent.py --submit --i-understand-risk --count 5 --proxy-port 1085 2>&1)
rc=$?
echo "$out" >>"$LOG"
echo "$(date '+%F %T') done rc=$rc" >>"$LOG"

# 何か起きた時だけ1行を stdout に出す（no_agent ジョブは stdout が通知になる）
if printf '%s' "$out" | grep -q "POST FAILED"; then
  echo "[reddit] 投稿失敗: $(printf '%s' "$out" | grep 'POST FAILED' | tail -1)"
elif printf '%s' "$out" | grep -q "posting:"; then
  echo "[reddit] 投稿実行: $(printf '%s' "$out" | grep 'posting:' | tail -1)"
fi
exit 0
