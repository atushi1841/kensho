#!/bin/bash
# .env weekly backup + md5 checksum
ENV="/mnt/d/Project2/kensho/.env"
BAKDIR="/mnt/d/Project2/kensho"
TS=$(date +%Y%m%d%H%M%S)
MD5FILE="$BAKDIR/.env.md5"

if [ ! -f "$ENV" ]; then
  echo "MISSING $ENV"
  exit 1
fi

md5=$(md5sum "$ENV" | awk '{print $1}')
cp "$ENV" "$BAKDIR/.env.bak-$TS"
chmod 600 "$BAKDIR/.env.bak-$TS"
echo "$md5  $TS" >> "$MD5FILE"
echo "BACKUP OK md5=$md5 ts=$TS"