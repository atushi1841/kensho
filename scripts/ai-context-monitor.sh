#!/bin/bash
# ============================================================
# ai-context-monitor.sh — Kensho AIチームのコンテキスト肥大監視
# 各AIジョブ（critic/worker/qa）の「応答部分（## Response以降）」の
# サイズをチェックし、Response truncated（出力長制限超過）のリスクを事前検知する。
#
# ポイント: 出力ファイル全体ではなく「応答部分」を監視する。
#   出力ファイルにはプロンプト（skill全文）も含まれるため、
#   全体サイズが大きくても応答が小さければ問題ない。
#   Response truncatedは「応答が出力制限に達する」ことで発生する。
#
# 2026-08-29 導入（criticのResponse truncated問題を踏まえた予防策）
# ============================================================
set -uo pipefail

OUTPUT_DIR="/home/atushi/.hermes/profiles/kensho-sweeps/cron/output"
LOG_FILE="/home/atushi/.hermes/profiles/kensho-sweeps/scripts/logs/ai-context-monitor.log"
mkdir -p "$(dirname "$LOG_FILE")"

# 応答サイズ閾値（バイト）: 30KB超 = 警告 / 60KB超 = 危険
WARN_THRESHOLD=30720   # 30KB
CRIT_THRESHOLD=61440   # 60KB

# 監視対象ジョブ（フォーマット: ジョブ名|job_id）
JOBS=(
  "critic|4baf143523e0"
  "worker|5e8ec4984bba"
  "qa|033ff6065ef7"
  "research-agent|0a52174180bd"
  "research-monetize|39d845fca735"
)

ts=$(date '+%Y-%m-%d %H:%M:%S')
alert_count=0
report_lines=()

for entry in "${JOBS[@]}"; do
  name="${entry%%|*}"
  job_id="${entry##*|}"
  job_dir="$OUTPUT_DIR/$job_id"

  if [ ! -d "$job_dir" ]; then
    continue
  fi

  # 最新の出力ファイルを取得
  latest=$(ls -t "$job_dir"/*.md 2>/dev/null | head -1)
  if [ -z "$latest" ]; then
    continue
  fi

  total_size=$(wc -c < "$latest")
  run_time=$(basename "$latest" .md)

  # 応答部分のサイズを計算（## Response 以降）
  # grep -n で行番号を取得 → その行以降を切り出してwc -c
  resp_line=$(grep -n "^## Response\|^# 実装結果\|^# QA検証結果\|^## 調査レポート" "$latest" | head -1 | cut -d: -f1)
  if [ -z "$resp_line" ]; then
    resp_size=0
    # Responseが見つからない＝エラー終了の可能性を確認
    if grep -q "Response truncated\|RuntimeError" "$latest"; then
      resp_size=$total_size  # エラー含みなので全体を監視対象に
      report_lines+=("❌ ERR  $name: エラー検出 ($run_time) — $(grep -m1 'RuntimeError' "$latest" | head -c 80)")
      alert_count=$((alert_count+1))
      continue
    fi
  else
    resp_size=$(tail -n +"$resp_line" "$latest" | wc -c)
  fi

  if [ "$resp_size" -ge "$CRIT_THRESHOLD" ]; then
    alert_count=$((alert_count+1))
    report_lines+=("🔴 CRIT $name: 応答${resp_size}B / 全体${total_size}B ($run_time) — Response truncatedリスク！スキル削減/出力制約が必要")
  elif [ "$resp_size" -ge "$WARN_THRESHOLD" ]; then
    alert_count=$((alert_count+1))
    report_lines+=("🟡 WARN $name: 応答${resp_size}B / 全体${total_size}B ($run_time) — 応答肥大化傾向")
  else
    report_lines+=("✅ OK  $name: 応答${resp_size}B / 全体${total_size}B ($run_time)")
  fi
done

# v155 (t_a085ab68): GO承認ゲート自己通過監視 — read-only（kanban.db mode=ro）・通知のみ。
# 事故パターン=本文「ユーザーGO必須/GO承認待ち/GO待ち」+ created(blocked)起票 + 人間GO
# （unblocked/promoted_manual）前にclaimed。検知時1行警告を logs/go_gate_watch.log へ追記し、
# go_gate_watch.sh 自身が notify.sh 経由でTelegram送信する（当スクリプトのstdoutは
# crontabで/dev/nullへ捨てられるため直接通知経路は必須）。台帳の強制block化は行わない。
GO_GATE_SH="/home/atushi/.hermes/profiles/kensho-sweeps/scripts/go_gate_watch.sh"
if [ -f "$GO_GATE_SH" ]; then
  GO_GATE_OUT=$(bash "$GO_GATE_SH" 2>/dev/null || true)
  if [ -n "$GO_GATE_OUT" ]; then
    while IFS= read -r gl; do
      [ -n "$gl" ] || continue
      alert_count=$((alert_count+1))
      report_lines+=("$gl")
    done <<< "$GO_GATE_OUT"
  fi
fi

# t_20c9c446 (QA run508提案): cron配置drift 5分監視 — repo↔profile md5漂移をその場で検知。
# 5f32176事故（repo修正済・cron配置が旧版のまま稼働）を朝1回でなく5分粒度で捕捉する。
# 通知は kensho_script_drift_watch.py が notify.sh 経由でdedup送信（当stdoutはcrontabで
# /dev/nullへ捨てられるため）。DRIFT/MISSING行のみstdoutに出る=cp同期後は無出力。
DRIFT_WATCH_PY="/home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho_script_drift_watch.py"
if [ -f "$DRIFT_WATCH_PY" ]; then
  DRIFT_OUT=$(python3 "$DRIFT_WATCH_PY" 2>/dev/null || true)
  if [ -n "$DRIFT_OUT" ]; then
    while IFS= read -r dl; do
      [ -n "$dl" ] || continue
      alert_count=$((alert_count+1))
      report_lines+=("$dl")
    done <<< "$DRIFT_OUT"
  fi
fi

# ログに記録
{
  echo "=== AI Context Monitor [$ts] ==="
  for line in "${report_lines[@]}"; do
    echo "  $line"
  done
} >> "$LOG_FILE"

# アラート時のみstdout出力（cronでTelegram通知に使う場合）
if [ "$alert_count" -gt 0 ]; then
  echo "[AIコンテキスト監視] ${alert_count}件のアラート ($ts)"
  for line in "${report_lines[@]}"; do
    echo "$line"
  done
fi

# 古いログは保持（肥大したら日次で回転）
if [ "$(wc -c < "$LOG_FILE" 2>/dev/null)" -gt 102400 ]; then
  mv "$LOG_FILE" "${LOG_FILE}.old"
fi
