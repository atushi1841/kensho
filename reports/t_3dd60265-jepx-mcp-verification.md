# t_3dd60265 — JEPX MCP actor + repo rework: verification evidence

## verification_evidence

### Success metric (acceptance)
$ curl -s -m 60 -w "\nHTTP:%{http_code}" "https://fruitful-quintessence--japan-jepx-mcp.apify.actor/rest/latest?area=tokyo"
{"date":"2026-09-17","area":"tokyo","area_label":"東京 (Tokyo)","price":15.24,"unit":"JPY/kWh","period":48,...}
HTTP:200

### GitHub repo no longer 404
$ git -C /home/atushi/.hermes/kanban/boards/kensho-ai-team/workspaces/t_3dd60265/japan-jepx-mcp ls-remote --heads origin
0b7f3f4957c9766d17fe3c37fec0c0d39957d70d	refs/heads/main

### Apify actor exists + Standby + build
$ curl -s -H "Authorization: Bearer $APIFY_TOKEN" "https://api.apify.com/v2/acts/BxstMzzxh8jq6UtfS" | head -c 900
{"data":{"id":"BxstMzzxh8jq6UtfS","name":"japan-jepx-mcp","username":"fruitful_quintessence","taggedBuilds":{"latest":{"buildNumber":"0.1.1"}},...}}

### 5 REST endpoints with token (all 200)
$ for p in "/rest/latest?area=tokyo" "/rest/date?area=tokyo&date=2026-09-15" "/rest/history" "/rest/cheapest" "/rest/areas"; do curl -s -o /dev/null -w "%{http_code} $p\n" -H "Authorization: Bearer $APIFY_TOKEN" "https://fruitful-quintessence--japan-jepx-mcp.apify.actor$p"; done
200 /rest/latest?area=tokyo
200 /rest/date?area=tokyo&date=2026-09-15
200 /rest/history
200 /rest/cheapest
200 /rest/areas

### Local TestClient smoke
$ timeout 90 python3 smoke_rest.py 2>&1 | tail -8
GET /rest/latest?area=tokyo -> 200
  price = 15.24 unit = JPY/kWh date = 2026-09-17
REST_SMOKE_OK
EXIT:0

### Deploy configs match spec
.actor/actor.json: usesStandbyMode=true, webServerMcpPath=/mcp
Dockerfile: CMD ["python", "-m", "src.main"]
manifest.json: 5 tools (get_latest_spot_price, get_spot_price_by_day, get_spot_price_history, get_cheapest_spot, list_spot_areas)

Result: all acceptance criteria PASS — success metric live 200 (15.24 JPY/kWh), GitHub repo 404 cleared (origin/main @ 0b7f3f4), actor japan-jepx-mcp Standby build 0.1.1. QA card t_ec9dee19 created for re-verification.
