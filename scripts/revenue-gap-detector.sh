#!/usr/bin/env bash
# revenue-gap-detector — 収益データ収集の自動健全性モニタリング
# revenue-daily.json の最新エントリと現在日の差を判定し、
# 収集遅延（≥2日）を検知したら警告を出力。
# cronから実行され、exit_code は常に0（検知のみ・破壊的操作なし）。
set -u

DATA_FILE="/mnt/d/Project2/kensho/data/revenue-daily.json"
GAP_THRESHOLD="${GAP_THRESHOLD:-2}"   # この日数以上の遅延で警告
TELEGRAM_WARN="${TELEGRAM_WARN:-1}"   # 1=Telegram通知有効

now_epoch=$(date +%s)
jst_offset=$((9 * 3600))
now_jst_epoch=$((now_epoch + jst_offset))

if [ ! -f "$DATA_FILE" ]; then
    echo "【収集遡延検知】revenue-daily.json が見つかりません: $DATA_FILE"
    exit 0
fi

# 最新エントリのdateフィールドを取得
last_date=$(python3 -c "
import json,sys
with open('$DATA_FILE') as f:
    d=json.load(f)
entries = d if isinstance(d,list) else [d]
print(entries[-1].get('date','unknown'))
" 2>/dev/null)

if [ -z "$last_date" ] || [ "$last_date" = "unknown" ]; then
    echo "【収集遡延検知】dateフィールドを読めません"
    exit 0
fi

last_epoch=$(date -d "$last_date" +%s 2>/dev/null)
if [ -z "$last_epoch" ]; then
    echo "【収集遡延検知】dateのパースに失敗: $last_date"
    exit 0
fi

last_jst_epoch=$((last_epoch + jst_offset))
diff_days=$(( (now_jst_epoch - last_jst_epoch) / 86400 ))

if [ "$diff_days" -ge "$GAP_THRESHOLD" ]; then
    echo "【収集遡延検知】最終収集日=$last_date 遅延=${diff_days}日（閾値=${GAP_THRESHOLD}日）"
    if [ "$TELEGRAM_WARN" = "1" ] && [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${TELEGRAM_CHAT_ID}" \
            -d "text=【収集遡延遡延検知】収益データの収集が${diff_days}日遅延しています（最終: $last_date）" \
            > /dev/null 2>&1 || true
    fi
else
    echo "【収集正常】最終収集日=$last_date 遅延=${diff_days}日"
fi

exit 0