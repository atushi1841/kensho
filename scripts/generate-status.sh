#!/usr/bin/env bash
# Kensho ステータスページ生成 v5.1 — Python scripts 呼び出し版
set -euo pipefail

PROJECT_DIR="/mnt/d/Project2/kensho"
export PROJECT_DIR

# データ生成
python3 /mnt/d/Project2/kensho/scripts/gen_status_data.py

# HTML生成
python3 /mnt/d/Project2/kensho/scripts/gen_status_html.py

echo "[OK] 生成完了: $PROJECT_DIR/kensho-status.html"
