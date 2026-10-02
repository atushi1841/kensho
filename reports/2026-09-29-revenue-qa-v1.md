# QA検証レポート (kensho-revenue-qa) — 2026-09-29 00:05 JST

## verification_evidence
$ bash ~/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh => score=100 streak=0 running=4 blocked=0 alert=OK escalation=false business_ok=true (前回 2026-09-28 18:15: score=60/streak=20/blocked=8/blocked=8→0 解消)
$ python3 -c "import sqlite3;c=sqlite3.connect('/home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db');[print(s,c.execute('select count(*) from tasks where status=?',(s,)).fetchone()[0]) for s in ['triage','ready','running','blocked','done','archived']]" => triage 0 / ready 1 / running 4 / blocked 0 / done 774 / archived 97
$ curl -s -H "Authorization: Bearer $APIFY_TOKEN_DEFAULT" "https://api.apify.com/v2/actors/DKzufUSvmuXNKHeYx" | python3 -c "import json,sys;d=json.load(sys.stdin)['data'];print('isPublic:',d.get('isPublic'))" => isPublic: True (前回 False→True 解決・API実測)
$ python3 -c "import json;d=json.load(open('data/revenue-daily.json'))[-1];print('date:',d['date'],'external_runs:',d['apify_ppe_external_runs']['actors'][0]['status'],'revenue:',d['apify_actual_revenue_usd'],'settle:',d['apify_settle_status'])" => date: 2026-09-28 / external_runs: ready / revenue: 0.0 / settle: zero_settle
$ ls reports/revenue-proposals/ | grep -c 0b6603ab => 0 (t_0b6603ab のWorker検証レポート未生成)
$ git status --porcelain | grep -E '\.(py|yaml|sh|js)$' | grep -v '^??' | wc -l => 8 (M 8件、うち収益関連は config.yaml/kensho_revenue_dashboard.py/deploy_feature_vector_actor.py)
$ python3 -c "import json;d=json.load(open('data/apify_ppe_external_runs_state.json'));print('triggered_actors:',len(d['last_trigger']))" => triggered_actors: 17
$ python3 -c "import json;d=json.load(open('data/revenue-daily.json'))[-1];print('verified_revenue:',d['apify_verified_revenue_usd'],'charged_items:',d['apify_verified_charged_items'],'external_users:',d['apify']['external_users_total'])" => verified_revenue: 0 / charged_items: 0 / external_users: 0

## 判定
- Technical 6/10 / Business KPI 2/10 / Cost Efficiency 8/10 → **conditional_pass**
- ループ健康度 score=100/streak=0/healthy → AIチーム健全（前回 60/degraded から回復、blocked 8→0）

## 次のアクション
- t_0b6603ab (running 5.6h): Worker検証レポート未生成 → 完了时报酬缺失
- t_2960f78c (running 0.5h): settle 自動検知＋実収益KPI化、external_runs=0 のままであり
- 【要ユーザー対応】Gumroad売上ゼロ継続 → 販促施策の実行検討。おすすめですすめます（GOで実行/対応をお願いします）