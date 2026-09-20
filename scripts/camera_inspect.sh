#!/usr/bin/env bash
set -u
cd /mnt/d/Project2/kensho
python3 - <<'PYEOF'
import csv, json
p="data/camera_monitor/model_price_diff_20260919.csv"
with open(p) as f:
    for r in csv.DictReader(f):
        print(r)
print("--- most recent candidates json if any ---")
import glob, os
for f in sorted(glob.glob("data/camera_monitor/sourcing_candidates_*.json")):
    d=json.load(open(f))
    print(f, "n=", len(d.get("candidates",[])))
    for c in d.get("candidates",[])[:8]:
        print("  ", c["model"], c["yahoo_title"][:40], "| 仕", c["sourcing_cost"], "→売", c["resale_price"], c["diff_pct"])
PYEOF