#!/usr/bin/env bash
# Poll until collect PID exits, then print artifact status + tail
set -u
PID="$1"
BASE="/mnt/d/Project2/kensho"
while kill -0 "$PID" 2>/dev/null; do
  sleep 30
done
echo "FINISHED"
echo "===collected_today.json==="
ls -la "$BASE/data/collected_today.json" 2>&1 || true
echo "===non_x report==="
ls -la "$BASE"/reports/non_x_manual_*.md 2>&1 || true
echo "===log tail==="
tail -50 "$BASE/logs/collect_20260920_190001.log"
