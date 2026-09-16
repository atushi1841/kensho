#!/usr/bin/env bash
# critic v169 (t_83759a2e): 応募停止の早期検知 — 稼働窓(09:00-23:00)内に当日ログの
# 「完了」行が閾値(既定120分)を超えて増えない＝応募停止と判定し、1回だけ通知文を出
# す。cron 30分毎に呼ばれ、平常時は [SILENT]（出力なし→配信なし）。適用ロジック/応募
# パイプラインの挙動は一切変更しない（検知層のみ）。
#
# 退出コード: 常に 0（処理成功）。但し内部エラーは 1。
#   --dry-run : 判定だけ表示（通知文を stdout に出す）。sentinel は書かない。
#
# 判定ロジック
#   1. 稼働窓外(H<09 or H>23) → SILENT
#   2. 当日 auto_YYYYMMDD.log の「完了」行を数える:
#        >0  → 最新完了行の時刻が閾値内なら稼働中(SILENT)
#        ==0 → 履歴(当日→日付降順で走査)の最新完了行の時刻から stall 時間を算出
#   3. stall 時間 >= 閾値 → 通知。sentinel に「その時の最新完了 epoch」を記録し、
#      送出は停止エピソードにつき1回だけ(次回は同じ epoch なので skip)。

PROJECT_DIR="${KENSO_STALL_PROJECT_DIR:-/mnt/d/Project2/kensho}"
LOG_DIR="${KENSO_STALL_LOGDIR:-$PROJECT_DIR/logs}"
THRESHOLD_MIN="${KENSO_STALL_THRESHOLD_MIN:-120}"
SENTINEL="${KENSO_STALL_SENTINEL:-/tmp/kensho_apply_stall.notified}"
WINDOW_START_H="${KENSO_STALL_WINDOW_START:-9}"
WINDOW_END_H="${KENSO_STALL_WINDOW_END:-23}"

DRY_RUN=0
DAYS=40
for a in "$@"; do
  [ "$a" = "--dry-run" ] && DRY_RUN=1
done

now_epoch=$(date +%s)
hour="${KENSO_STALL_HOUR:-$(date +%H)}"
hour10=$((10#$hour))

# ── 1. 稼働窓チェック ──
if [ "$hour10" -lt "$WINDOW_START_H" ] || [ "$hour10" -gt "$WINDOW_END_H" ]; then
  [ "$DRY_RUN" -eq 1 ] && echo "SILENT: 稼働窓外 (H=$hour10)"
  exit 0
fi

# ── 2. 当日ログ判定 ──
today=$(date +%Y%m%d)
today_log="$LOG_DIR/auto_${today}.log"
today_count=0
if [ -f "$today_log" ]; then
  today_count=$(grep -c '完了' "$today_log" 2>/dev/null || true)
fi
today_count=$((10#$today_count))

last_epoch=""
last_src=""
find_last_completion() {
  # 日付降順で daily ログを走査し「完了」を含む最新行の epoch を求める
  local i
  for i in $(seq 0 "$DAYS"); do
    local d suffix
    suffix=$(date -d "-$i day" +%Y%m%d 2>/dev/null) || continue
    local f="$LOG_DIR/auto_${suffix}.log"
    [ -f "$f" ] || continue
    local line
    line=$(grep '完了' "$f" 2>/dev/null | tail -1)
    [ -z "$line" ] && continue
    local dstr tstr
    dstr=$(echo "$line" | awk '{print $1}')
    tstr=$(echo "$line" | awk '{print $2}')
    [ -z "$dstr" ] || [ -z "$tstr" ] && continue
    local ep
    ep=$(date -d "$dstr $tstr" +%s 2>/dev/null) || continue
    last_epoch=$ep
    last_src="$f"
    return 0
  done
  return 1
}

if [ "$today_count" -gt 0 ]; then
  # 当日に完了行あり → 最新 line の時刻
  line=$(grep '完了' "$today_log" 2>/dev/null | tail -1)
  dstr=$(echo "$line" | awk '{print $1}')
  tstr=$(echo "$line" | awk '{print $2}')
  last_epoch=$(date -d "$dstr $tstr" +%s 2>/dev/null || echo 0)
  last_src="$today_log"
else
  find_last_completion || last_epoch=0
fi

if [ -z "$last_epoch" ] || [ "$last_epoch" -le 0 ]; then
  # 完了履歴が一切ない＝完全未稼働 → 閾値超え扱い（停止）にする
  stall_min=$(( THRESHOLD_MIN + 1 ))
  last_epoch=0
  last_src="(recent ${DAYS}d logs に完了履歴なし)"
else
  stall_min=$(( (now_epoch - last_epoch) / 60 ))
fi

# ── 3. 閾値・送出 ──
if [ "$stall_min" -lt "$THRESHOLD_MIN" ]; then
  [ "$DRY_RUN" -eq 1 ] && echo "SILENT: 稼働中 (stall=${stall_min}min, 完了=$today_count)"
  exit 0
fi

notify_text="[Kensho] 応募停止検知: ${stall_min}分「完了」行なし (今日${today_count}件, src=${last_src})"

if [ "$DRY_RUN" -eq 1 ]; then
  echo "NOTIFY-STAGE: stall=${stall_min}min >= ${THRESHOLD_MIN}min"
  echo "$notify_text"
  exit 0
fi

# 送出（1回/エピソード）: sentinel が今の last_epoch と同じなら skip
prev=""
[ -f "$SENTINEL" ] && prev=$(cat "$SENTINEL" 2>/dev/null)
if [ "$prev" = "$last_epoch" ]; then
  exit 0  # 既に同エピソードを通知済み → SILENT
fi

echo "$notify_text"
echo "$last_epoch" > "$SENTINEL" 2>/dev/null
exit 0
