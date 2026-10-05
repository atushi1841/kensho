#!/bin/bash
# .env monitor: detect loss/corruption, auto-restore, notify via Telegram
ENV="/mnt/d/Project2/kensho/.env"
BAKDIR="/mnt/d/Project2/kensho"
MD5FILE="$BAKDIR/.env.md5"
LOG="$BAKDIR/logs/auto_$(date +%Y%m%d).log"
mkdir -p "$BAKDIR/logs"

has_telegram() { command -v curl >/dev/null && grep -q "TELEGRAM_BOT_TOKEN" "$ENV" 2>/dev/null; }
tg_msg() {
  local msg="$1"
  local bot=$(grep '^TELEGRAM_BOT_TOKEN=' "$ENV" 2>/dev/null | cut -d= -f2)
  local chat=$(grep '^TELEGRAM_CHAT_ID=' "$ENV" 2>/dev/null | cut -d= -f2)
  [ -z "$bot$chat" ] && return 1
  curl -s -X POST "https://api.telegram.org/bot$bot/sendMessage" \
    -d chat_id="$chat" -d text="$msg" >/dev/null 2>&1
}

# Check existence
if [ ! -f "$ENV" ]; then
  echo "[$(date)] ALERT: .env MISSING" >> "$LOG"
  # Restore latest backup
  latest=$(ls -t "$BAKDIR"/.env.bak-* 2>/dev/null | head -1)
  if [ -n "$latest" ]; then
    cp "$latest" "$ENV" && chmod 600 "$ENV"
    echo "[$(date)] RESTORED from $latest" >> "$LOG"
    has_telegram && tg_msg "⚠ .env復旧: $latest → .env"
  else
    has_telegram && tg_msg "🚨 .env消失＆バックアップなし: 手動対応必要"
  fi
  exit 1
fi

# Check md5
current=$(md5sum "$ENV" | awk '{print $1}')
if [ -f "$MD5FILE" ]; then
  prev=$(tail -1 "$MD5FILE" | awk '{print $1}')
  if [ "$current" != "$prev" ]; then
    echo "[$(date) WARN] md5 mismatch: prev=$prev cur=$current" >> "$LOG"
    has_telegram && tg_msg "⚠ .env変更検知 md5=$current"
  fi
fi

# Update md5
echo "$current  $(date +%Y%m%d%H%M%S)" >> "$MD5FILE"
echo "[$(date)] OK md5=$current" >> "$LOG"
exit 0