#!/bin/bash
# t_1b2ecfa1: 商品説明の実更新を読み戻し検証 + cron一覧
cd "$(dirname "$0")/.." || exit 1
set -a; [ -f .env ] && . ./.env; set +a
echo "===product description readback==="
curl -s "https://api.gumroad.com/v2/products/VoJxWx8UC0KN7lDRsOts7A==?access_token=$GUMROAD_TOKEN" \
  | python3 -c '
import sys, json
d = json.load(sys.stdin)
p = (d.get("product") or {})
desc = p.get("description") or ""
print("name:", p.get("name"))
print("desc len:", len(desc))
print("desc head:", desc[:130].replace("\n"," ")[:130])
print("has_サマリ:", "サマリ" in desc)
'
