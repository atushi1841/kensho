#!/usr/bin/env bash
# Kensho ステータスページ生成 v5.2 — Python scripts 呼び出し版
set -euo pipefail

PROJECT_DIR="/mnt/d/Project2/kensho"
export PROJECT_DIR

# アカウント×WiFi の live 情報（Windows実測）を更新 — 失敗しても生成は続行
python3 /mnt/d/Project2/kensho/scripts/refresh_wifi_map.py || echo "[warn] wifi map 更新をスキップ"

# データ生成
python3 /mnt/d/Project2/kensho/scripts/gen_status_data.py

# HTML生成
python3 /mnt/d/Project2/kensho/scripts/gen_status_html.py

echo "[OK] 生成完了: $PROJECT_DIR/kensho-status.html"
