# QA検証レポート (kensho-revenue-qa) — 2026-09-28 18:15 JST

## verification_evidence
$ bash ~/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh => score=60 streak=20 blocked=8 running=0 degraded business_ok=false
$ python3 -c "import sqlite3;c=sqlite3.connect('/home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db');[print(s,c.execute('select count(*) from tasks where status=?',(s,)).fetchone()[0]) for s in ['triage','ready','running','blocked','done','archived']]" => triage 0 / ready 1 / running 0 / blocked 8 / done 759 / archived 96
$ curl -s "https://api.apify.com/v2/actors/DKzufUSvmuXNKHeYx" -H "Authorization: Bearer $(grep APIFY_TOKEN_DEFAULT .env | head -1 | cut -d= -f2)" => isPublic=False (API経由不可、Console手動設定必要)
$ .venv/bin/python -m pytest tests/test_apify_ppe_external_views.py tests/test_gumroad_promo.py tests/test_apify_ppe_store_seo.py tests/test_apify_run_monitor_retry.py tests/test_apify_seo_apply.py tests/test_apify_seo_audit.py tests/test_apify_seo_effect.py tests/test_gumroad_cookies_guard.py tests/test_non_api_revenue_hunter_gate.py tests/test_revenue_collect.py -q => 233 passed
$ git status --porcelain | grep -E '\.(py|yaml|sh|js)$' | wc -l => 124 (M 5 / ?? 119)
$ grep -n "apify\|APIFY\|gumroad\|GUMROAD" config.yaml => 0 hits
$ python3 -c "import json;d=json.load(open('apify-figure-price/.actor/actor.json'));print('input:', 'input' in d, 'output:', 'output' in d)" => input: True output: True
$ python3 -c "import json;d=json.load(open('apify-figure-price/actor.json'));print('input:', 'input' in d, 'output:', 'output' in d)" => input: True output: False

## 判定
- Technical 4/10 / Business KPI 2/10 / Cost Efficiency 8/10 → **fail**
- ループ健康度 score=60(degraded) / streak=20 / business_ok=false → AIチーム停滞中

## 次のアクション
【要ユーザー対応】Apify Console で japan-anime-figure-price-data を Public に変更 → t_61354640完了→連鎖unblock。おすすめですすめます（GOで実行/対応をお願いします）