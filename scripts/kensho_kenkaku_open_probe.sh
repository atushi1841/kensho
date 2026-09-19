#!/usr/bin/env bash
# KENKAKU オープン懸賞カテゴリ(101/103系列)のX URL埋込を調査
out=/tmp/kp_probe.txt
: > "$out"
for pid in 101010000 101020000 101030000 101040000 101050000 101060000 \
           101070000 101080000 101090000 101100000 101110000 \
           103010000 103020000 103030000 103040000 103050000 103100000 \
           103110000 103120000 103130000 103140000; do
  curl -s -o /tmp/kp_page.html --max-time 12 \
     -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36" \
     "https://www.ken-kaku.com/cgi-bin/present/present.cgi?id=$pid"
  n=$(grep -oE "x\.com/[a-zA-Z0-9_]+/status/[0-9]+|twitter\.com/[a-zA-Z0-9_]+/status/[0-9]+" /tmp/kp_page.html 2>/dev/null | sort -u | wc -l)
  title=$(grep -oE "<title>[^<]*" /tmp/kp_page.html 2>/dev/null | head -1 | sed 's/<title>//')
  echo "$pid code=$? x=$n | $title" >> "$out"
  sleep 0.6
done
cat "$out"
