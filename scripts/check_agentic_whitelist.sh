#!/bin/bash
# check_agentic_whitelist.sh — Apify agentic/x402 whitelist スキャン（恒久版）
# 出典: critic v87 (t_370e65d0) workspace verify_v87.py を repo 恒久化 (critic v89 / t_2713a67b)
# 使い方: bash scripts/check_agentic_whitelist.sh
# 出力: JSON {total, whitelisted, not_whitelisted:[...], ppe_gaps:[...], ppe_gap_count}
# 成功条件: exit 0 かつ whitelisted>=62 かつ ppe_gap_count<=2（2026-09-10実測ベースライン）
set -uo pipefail

ENV_FILE="${KENSHO_ENV:-/mnt/d/Project2/kensho/.env}"
[ -f "$ENV_FILE" ] || { echo '{"error":"env file not found: '"$ENV_FILE"'"}' ; exit 1; }

TMP=$(mktemp); trap 'rm -f "$TMP"' EXIT

APIFY_TOKEN_DEFAULT=$(grep '^APIFY_TOKEN_DEFAULT=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' | tr -d ' ')
[ -n "$APIFY_TOKEN_DEFAULT" ] || { echo '{"error":"APIFY_TOKEN_DEFAULT not set in '"$ENV_FILE"'"}'; exit 1; }

# GET /v2/store?limit=1000&username=fruitful_quintessence
# 教訓(v87): username filter + limit=1000 必須。community scan は count が 1000 で頭打ちになり誤読する
curl -s --max-time 120 \
  -H "Authorization: Bearer ${APIFY_TOKEN_DEFAULT}" \
  -H "User-Agent: Mozilla/5.0" \
  "https://api.apify.com/v2/store?limit=1000&username=fruitful_quintessence" -o "$TMP" \
  || { echo '{"error":"apify store request failed"}'; exit 1; }

python3 - "$TMP" <<'PYEOF'
import json, sys

try:
    with open(sys.argv[1]) as f:
        resp = json.load(f)
    items = resp["data"]["items"]
except Exception as e:
    print(json.dumps({"error": "parse failed: %s" % e}))
    sys.exit(1)

wl = sorted(i["name"] for i in items if i.get("isWhiteListedForAgenticPayments"))
notw = sorted(i["name"] for i in items if not i.get("isWhiteListedForAgenticPayments"))
# PPE なのに whitelist False の gap（report 手順3: 2週間以上 False なら support へ）
# 実測(2026-09-10): store item の課金フィールドは currentPricingInfo（pricingInfo/currentPricingModel は存在しない）
def pricing_model(i):
    pi = i.get("currentPricingInfo") or {}
    return pi.get("pricingModel") or i.get("currentPricingModel") or ""

ppe_gaps = sorted(
    i["name"] for i in items
    if not i.get("isWhiteListedForAgenticPayments")
    and pricing_model(i) == "PAY_PER_EVENT"
)

out = {
    "username": "fruitful_quintessence",
    "total": len(items),
    "whitelisted": len(wl),
    "not_whitelisted": notw,
    "ppe_gaps": ppe_gaps,
    "ppe_gap_count": len(ppe_gaps),
}
print(json.dumps(out, ensure_ascii=False, indent=1))
# 成功条件: whitelisted>=62 かつ ppe_gap_count<=2（ベースラインが動いたら critic が更新）
sys.exit(0 if len(wl) >= 62 and len(ppe_gaps) <= 2 else 2)
PYEOF
rc=$?
if [ $rc -eq 2 ]; then
  echo "WARN: baseline drift (whitelisted<62 or ppe_gaps>2)" >&2
fi
exit $rc
