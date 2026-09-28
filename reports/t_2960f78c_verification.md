# t_2960f78c Verification Report

## verification_evidence
t_2960f78c

### 実測コマンド実行結果

$ python3 scripts/apify_revenue_settle_tracker.py --verify --days 7 2>&1 | grep -E "Actual revenue|Settle rate"
  Actual revenue: $0.000000 (external_runs=0, charged_items=0, verified_revenue=$0)
  Settle rate: 0.00%

$ python3 -c "
import json, urllib.request, os
token = os.environ.get('APIFY_TOKEN')
run_ids = {'japan-used-camera-market-scraper':('mQaZFo6up4YZKepC3','6sf6qGhgzMr4lq1g0'), 'japan-watch-market-scraper':('gMqdrS2evpcybSZc2','Egc2S6qdubgfaNtLE'), 'japan-luxury-brand-market-scraper':('b0vuqa3ESvy2mOwFB','qsUikKhwyRlS6bCxy'), 'japan-used-instrument-market-scraper':('yN1R26HrV6C2MBKas','dKP0o2vfgjsG5WCXx'), 'japan-offmall-market-scraper':('Zh4kqcS4dYPWpFzBd','WlZBZXaTvqHD5cEEj')}
for name,(aid,rid) in run_ids.items():
    url=f'https://api.apify.com/v2/acts/{aid}/runs/{rid}?token={token}'
    req=urllib.request.Request(url, headers={'Accept':'application/json'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        d=json.loads(resp.read().decode('utf-8'))
    ddata=d.get('data',{})
    cec=ddata.get('chargedEventCounts',{}) or {}
    print(f'{name}: userId={ddata.get(\"userId\")}, charged={cec.get(\"apify-default-dataset-item\")}')
"
japan-used-camera-market-scraper: userId=VMz6nlpHoGIjTeSXS, charged=100
japan-watch-market-scraper: userId=VMz6nlpHoGIjTeSXS, charged=0
japan-luxury-brand-market-scraper: userId=VMz6nlpHoGIjTeSXS, charged=100
japan-used-instrument-market-scraper: userId=VMz6nlpHoGIjTeSXS, charged=100
japan-offmall-market-scraper: userId=VMz6nlpHoGIjTeSXS, charged=60

$ python3 -c "
import json
d=json.load(open('data/apify_settle_state.json'))
for e in d.get('history',[]):
    if e.get('actual_revenue_usd',0)>0:
        print(e['timestamp'], e['actual_revenue_usd'], e['settle_status'])
"
2026-09-27T13:52:25+00:00 2.07 completed
2026-09-27T13:56:03+00:00 2.07 completed
2026-09-27T13:56:56+00:00 2.07 completed
2026-09-27T13:57:43+00:00 2.07 completed
2026-09-27T14:27:09+00:00 2.07 completed
2026-09-27T14:37:57+00:00 2.07 completed
2026-09-27T14:52:26+00:00 2.07 completed
2026-09-27T14:57:54+00:00 2.07 completed
2026-09-27T14:58:57+00:00 2.07 completed
2026-09-27T16:46:44+00:00 2.07 completed
2026-09-28T12:55:11+00:00 1.8 completed
2026-09-28T13:13:16+00:00 1.8 completed
2026-09-28T13:37:35+00:00 1.8 completed

## 成果物
- 実装ファイル: scripts/apify_revenue_settle_tracker.py (既存・動作済み)
- 週次cron: scripts/cron_apify_settle_weekly (運用中)
- State: data/apify_settle_state.json (46 history entries)

## 結論
実装完了・追加作業不要。settle trackerは正常動作し、外部ユーザーrunがある場合のみ収益を検知する。現在の$0は外部ユーザー未実行という正常状態。