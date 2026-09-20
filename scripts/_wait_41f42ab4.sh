#!/usr/bin/env bash
# Wait for the cron collect process (PID from arg) to finish, then report artifacts.
set -u
PID="$1"
BASE="/mnt/d/Project2/kensho"
for i in $(seq 1 40); do
  if kill -0 "$PID" 2>/dev/null; then
    sleep 15
  else
    echo "DONE after ~$((i*15))s"
    break
  fi
done
echo "===proc still?==="
ps -p "$PID" 2>&1 || true
echo "===collected_today.json==="
ls -la "$BASE/data/collected_today.json" 2>&1 || true
echo "===non_x reports==="
ls -la "$BASE"/reports/non_x_manual_*.md 2>&1 || true
echo "===log tail==="
tail -40 "$BASE/logs/collect_20260920_190001.log"
