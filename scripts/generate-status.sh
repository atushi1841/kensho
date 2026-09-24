#!/usr/bin/env bash
# Kensho ステータスページ生成 v5.2 — Python scripts 呼び出し版
set -euo pipefail

PROJECT_DIR="/mnt/d/Project2/kensho"
export PROJECT_DIR

# アカウント×WiFi の live 情報（Windows実測）を更新 — 失敗しても生成は続行
python3 /mnt/d/Project2/kensho/scripts/refresh_wifi_map.py || echo "[warn] wifi map 更新をスキップ"

# ── t_e2b356ce: 同一 tick の PROXY-CHECK 完走を待つ（偽 dead_proxy / 無音凍結の防止）──
# 本スクリプトは crontab の */15 で kensho-auto-apply.sh と同時刻に起動する。apply tick の
# [PROXY-CHECK] 行は tick 開始の16〜34秒後に書かれるため、待たずに生成すると gen_status_data.py は
# 「生成時刻-2分以降」の行を見つけられず status を一切更新しない（1 tick 偽 dead_proxy は防げるが
# proxy 状態が無音で凍結する）。tick が動いている間だけ、同一 tick の [PROXY-CHECK] 行が現れるまで
# 最大60秒待つ。tick が20分以上動いていない（パイプライン停止中）ときは即座に諦める。
LOG_FILE="$PROJECT_DIR/logs/auto_$(date +%Y%m%d).log"
_wait_until=$(( $(date +%s) + 60 ))
while [ "$(date +%s)" -lt "$_wait_until" ]; do
  _tick_line=$(grep -nE '^\[[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}\]' "$LOG_FILE" 2>/dev/null | tail -1 | cut -d: -f1 || true)
  if [ -z "${_tick_line:-}" ]; then break; fi
  _tick_ts=$(sed -n "${_tick_line}p" "$LOG_FILE" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}' || true)
  _tick_epoch=$(date -d "${_tick_ts:-@0}" +%s 2>/dev/null || echo 0)
  _age=$(( $(date +%s) - _tick_epoch ))
  if [ "$_age" -gt 1200 ]; then break; fi
  if [ "$_age" -le 180 ] && tail -n +"$_tick_line" "$LOG_FILE" | grep -q '\[PROXY-CHECK\]'; then break; fi
  sleep 5
done

# データ生成
python3 /mnt/d/Project2/kensho/scripts/gen_status_data.py

# HTML生成
python3 /mnt/d/Project2/kensho/scripts/gen_status_html.py

echo "[OK] 生成完了: $PROJECT_DIR/kensho-status.html"
