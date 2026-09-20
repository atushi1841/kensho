#!/usr/bin/env bash
set -u
cd /mnt/d/Project2/kensho
python3 - <<'PYEOF'
import csv
f="data/camera_monitor/matched_pairs_20260919.csv"
try:
    rows=list(csv.DictReader(open(f, encoding='utf-8-sig')))
except FileNotFoundError:
    print("no file"); raise SystemExit
print(f, len(rows))
for r in rows[:14]:
    print(" ", r["model"], "cost",r["cost"],"resale",r["resale"],"diff%",r["diff_pct"],"|",r["yahoo"][:38],"|",r["suruga"][:30])
PYEOF