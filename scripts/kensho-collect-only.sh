#!/bin/bash
# kensho-collect-only.sh — 収集のみ実行（深夜用）
cd /mnt/d/Project2/kensho || exit 1
source ~/kensho-venv/bin/activate

LOG_FILE="/mnt/d/Project2/kensho/logs/collect_$(date +%Y%m%d_%H%M%S).log"
exec python -c "
import sys
sys.path.insert(0, '.')
from kensho.scraping.collector import collect
from kensho.core.config import load
cfg = load()
success, errors, total = collect(cfg)
print(f'収集完了: {success}成功/{errors}エラー/{total}合計')
" >> "$LOG_FILE" 2>&1
