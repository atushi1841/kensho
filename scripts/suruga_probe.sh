#!/usr/bin/env bash
set -u
cd /mnt/d/Project2/suruga-scraper
PY=/home/atushi/.hermes/hermes-agent/venv/bin/python3
timeout 110 $PY - <<'PYEOF'
import sys
sys.path.insert(0, "src")
from scraper import scrape
p = scrape("ILCE-7M4", max_pages=1, in_stock_only=False, output="_probe_r7m4.json")
print("return:", p)
import json, os
fn = "data/_probe_r7m4.json"
if os.path.exists(fn):
    d = json.load(open(fn))
    items = d.get("items", [])
    print("suruga items:", len(items))
    for i in items[:5]:
        print("  ", i.get("name"), "| used", i.get("used_price_jpy"), "| new", i.get("new_price_jpy"), "| stock", i.get("in_stock"))
PYEOF
echo "rc=$?"