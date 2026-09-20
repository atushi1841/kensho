#!/usr/bin/env bash
# camera_monitor_7d_daily.sh — Z9/Z8 7日間再現性監視 日次ラッパー(t_990fb91c)
#
# 毎日1回 camera_monitor.py を実行し、出力 model_price_diff_<DATE>.csv から
# Nikon Z8 / Nikon Z9 の行だけを抽出して data/camera_monitor/7d_repro_audit.csv に追記する。
# - 既存の監視ロジック(camera_monitor.py)には一切手を加えない。
# - 冪等: 当日分のレコードが既に7d_repro_audit.csvに存在すれば実行をスキップ
#   (cron再発火・手動重複実行による二重追記を防止)。
# - Bot回避のため1日1回のみ(頻度はcrontab側で担保)。
set -uo pipefail

cd /mnt/d/Project2/kensho || exit 1
ROOT=/mnt/d/Project2/kensho
DATA="$ROOT/data/camera_monitor"
AUDIT="$DATA/7d_repro_audit.csv"
LOG="$ROOT/reports/camera_monitor_7d_daily_$(date +%Y%m%d).log"
TODAY=$(date +%Y%m%d)
LOCK="$DATA/.7d_daily.lock"

mkdir -p "$DATA"

# 排他ロック(並列cron発火時の二重実行防止)
exec 9>"$LOCK"
if ! flock -n 9; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') SKIP: another instance running" >> "$LOG"
    exit 0
fi

# 冪等チェック: 当日分が既にauditに存在
if [ -f "$AUDIT" ] && grep -q "^${TODAY}," "$AUDIT"; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') SKIP: audit already has ${TODAY}" >> "$LOG"
    exit 0
fi

# 1) 本番収集を実行(フル30モデル、既存ロジック)。失敗時ログ記録し次回再実行に委ねる。
echo "$(date '+%Y-%m-%d %H:%M:%S') RUN: python3 -m scripts.camera_monitor" >> "$LOG"
if ! python3 -m scripts.camera_monitor >> "$LOG" 2>&1; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') ERROR: camera_monitor failed; will retry next cron" >> "$LOG"
    exit 1
fi
DIFF="$DATA/model_price_diff_${TODAY}.csv"
if [ ! -f "$DIFF" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') ERROR: model_price_diff_${TODAY}.csv not produced" >> "$LOG"
    exit 1
fi

# 2) Z9/Z8 行を抽出して audit に追記(初回はヘッダ作成)
if [ ! -f "$AUDIT" ]; then
    echo "date,model,yahoo_buynow,suruga_items,matched_pairs,median_diff_pct,max_diff_pct" > "$AUDIT"
fi
# BOM付きCSV対策: 1行目BOMを除去した上でZ9/Z8行のみ抽出
python3 - "$DIFF" "$AUDIT" "$TODAY" <<'PY'
import csv, sys, os
src, aud, today = sys.argv[1], sys.argv[2], sys.argv[3]
headers = None
records = []
with open(src, "r", encoding="utf-8-sig", newline="") as f:
    for row in csv.DictReader(f):
        model = (row.get("model") or "").strip()
        if model in ("Nikon Z8", "Nikon Z9"):
            records.append({
                "date": today,
                "model": model,
                "yahoo_buynow": row.get("yahoo_buynow") or "",
                "suruga_items": row.get("suruga_items") or "",
                "matched_pairs": row.get("matched_pairs") or "",
                "median_diff_pct": row.get("median_diff_pct") or "",
                "max_diff_pct": row.get("max_diff_pct") or "",
            })
if not records:
    print(f"{today}: no Z8/Z9 rows in {src}", file=sys.stderr)
# 既存audit読み込み
existing = set()
if os.path.exists(aud):
    with open(aud, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            existing.add((row.get("date"), row.get("model")))
new_rows = [r for r in records if (r["date"], r["model"]) not in existing]
if not new_rows:
    print(f"{today}: Z8/Z9 already in audit, no append")
    sys.exit(0)
with open(aud, "a", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(records[0].keys()))
    w.writerows(new_rows)
print(f"{today}: appended {len(new_rows)} Z8/Z9 rows -> {aud}")
PY
echo "$(date '+%Y-%m-%d %H:%M:%S') DONE append" >> "$LOG"
exit 0
