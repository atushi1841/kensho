#!/bin/bash
# data_journalism_week.sh — AIデータジャーナリズム週次レポート生成 (t_0b949bda)
#
# 用途: cron / 手動いずれからも「統計JSON → レポート本体 → ブログ下書き」を
#       同一手順で再生成する。生成器は決定的（同一入力→同一 fingerprint）なので、
#       何度実行しても内容は変わらない（generated_at 行のみ更新）。
#
# 使い方:
#   bash scripts/data_journalism_week.sh                  # 今週分を生成（履歴スナップショット付き）
#   bash scripts/data_journalism_week.sh --week 2026W39   # 週を指定して再生成
#   bash scripts/data_journalism_week.sh --dry-run        # テンプレ整合性チェックのみ
#
# 引数なし = 本番動作。cron の no_agent 実行は引数なしで `bash <path>` されるため、
# 既定が本番になるよう設計している（生成を止めたいときだけ --dry-run を明示する）。
#
# 出力:
#   reports/journalism/<week>.md      … レポート本体
#   reports/journalism/<week>.json    … 統計JSON（AIチームの下流入力）
#   reports/journalism/drafts/*.md    … dev.to / Qiita 投稿用下書き
#   logs/data_journalism_<date>.log   … 実行ログ

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/mnt/d/Project2/kensho}"
LOG_DIR="$PROJECT_DIR/logs"
RUN_LOG="$LOG_DIR/data_journalism_$(date +%Y%m%d).log"

mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$RUN_LOG"; }

WEEK_ARGS=()
DRY_RUN=0
while [ $# -gt 0 ]; do
  case "$1" in
    --week) WEEK_ARGS+=(--week "$2"); shift 2 ;;
    --week=*) WEEK_ARGS+=(--week "${1#--week=}"); shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

log "data_journalism start (dry_run=$DRY_RUN)"

# 1) テンプレート整合性ゲート（プレースホルダ欠落を生成前に落とす）
if ! python3 scripts/kensho_data_journalism.py --check-template >>"$RUN_LOG" 2>&1; then
  log "NG: template check failed"
  exit 1
fi

if [ "$DRY_RUN" = "1" ]; then
  log "dry-run: template ok / generation skipped"
  exit 0
fi

# 2) 生成（--snapshot で履歴を1件増やし、次回の前週比の母集団を用意する）
python3 scripts/kensho_data_journalism.py "${WEEK_ARGS[@]}" --snapshot >>"$RUN_LOG" 2>&1

# 3) 直前に生成された統計JSONを特定（生成器自身の出力なので週ラベル計算を重複させない）
STATS="$(ls -1t "$PROJECT_DIR"/reports/journalism/*.json | head -1)"
REPORT="${STATS%.json}.md"
WEEK_LABEL="$(basename "$STATS" .json)"

if [ ! -f "$STATS" ] || [ ! -f "$REPORT" ]; then
  log "NG: outputs missing (stats=$STATS report=$REPORT)"
  exit 1
fi

# 4) サマリ（cron の no_agent はこの stdout をそのまま保存する）
python3 - "$STATS" "$REPORT" <<'PY' | tee -a "$RUN_LOG"
import json
import sys

stats_path, report_path = sys.argv[1], sys.argv[2]
s = json.load(open(stats_path, encoding="utf-8"))
week = s["week_label"]
print(f"week       : {week}")
print(f"report     : {report_path}")
print(f"stats      : {stats_path}")
print(f"campaigns  : {s['total_campaigns']:,}")
print(f"entries    : {s['total_entries']:,}")
print(f"seats      : {s['total_seats']:,}")
print(f"wins       : {s['wins']['matched']}/{s['wins']['total']} 突合")
print("drafts     : reports/journalism/drafts/devto-" + week + ".md, qiita-" + week + ".md")
print(f"fingerprint: {s['fingerprint'][:16]}")
PY

log "data_journalism done (week=$WEEK_LABEL)"
