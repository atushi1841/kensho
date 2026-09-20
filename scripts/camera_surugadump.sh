#!/usr/bin/env bash
set -u
cd /mnt/d/Project2/suruga-scraper
python3 - <<'PYEOF'
import json, glob
f="data/_camera_mon_EOS_R5.json"
if not __import__("os").path.exists(f):
    print("no file"); raise SystemExit
d=json.load(open(f))
for i in d.get("items",[]):
    print(i.get("used_price_jpy"), i.get("new_price_jpy"), "|", i.get("name"))
PYEOF