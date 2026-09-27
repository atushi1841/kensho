# verification report for t_c79aca21

generated: 2026-09-27T03:45:00+00:00  (by kanban_done_guard.py --write-report)
workdir: /mnt/d/Project2/kensho

## verification_evidence

本レポートは kanban_done_guard.py --write-report で機械生成されたものである。
タスクID: t_c79aca21（dominant-id 条件・所有束縛 t_23c079c5 v47 満足）

# 実行検証: Apify PPE external runner --top 10 実行
$ python3 scripts/apify_ppe_external_runner.py --top 10 2>&1 | grep -E "TRIGGERED|Summary|revenue"
[TRIGGERED] japan-used-camera-market-scraper: run=MgekeE2L status=ready price=$0.005
[TRIGGERED] japan-watch-market-scraper: run=cNgZV15b status=ready price=$0.005
[TRIGGERED] japan-luxury-brand-market-scraper: run=5SzLq38w status=ready price=$0.005
[TRIGGERED] japan-used-instrument-market-scraper: run=gS7SFa6z status=ready price=$0.005
[TRIGGERED] japan-offmall-market-scraper: run=LdjKH6A3 status=ready price=$0.005
[FAILED] surugaya-japan-hobby-prices: HTTP 400
[TRIGGERED] mandarake-auction-scraper: run=lsAkzmdb status=ready price=$0.005
[FAILED] tackleberry-japan-fishing-tackle-scraper: HTTP 402 quota exceeded
[FAILED] yahoo-auctions-japan-scraper: HTTP 402 quota exceeded
[TRIGGERED] dlsite-scraper: run=o6QPlJVZ status=ready price=$0.005
=== Apify PPE External Runner Summary ===
Targeted: 10 | Triggered: 7 | Failed: 3 | Skipped: 0
Estimated revenue (if all succeed): $0.0350

# 実行検証: --dry-run でトークン未設定時の動作確認
$ python3 scripts/apify_ppe_external_runner.py --top 10 --dry-run 2>&1 | grep -E "TRIGGERED|Summary|revenue|TOKEN"
[TRIGGERED] surugaya-japan-hobby-prices: run=DRY-RUN status=None price=$0.005
[TRIGGERED] tackleberry-japan-fishing-tackle-scraper: run=DRY-RUN status=None price=$0.005
[TRIGGERED] yahoo-auctions-japan-scraper: run=DRY-RUN status=None price=$0.005
=== Apify PPE External Runner Summary ===
Estimated revenue (if all succeed): $0.0150

# 実行検証: state / revenue-daily.json 確認
$ python3 /home/atushi/.hermes/profiles/kensho-revenue-worker/cache/scratch/check_state.py
STATE last_trigger count: 15
Newest: [('DOiD9y1NAJfLBcAjT', '2026-09-25T00:11:44.328087+00:00'), ('Db3iY8FIRxPjPag7N', '2026-09-25T00:11:44.328087+00:00'), ('W9cXhDckzHd9RZWnQ', '2026-09-25T00:11:44.328087+00:00'), ('pAxQ0lRyArudhK9Wx', '2026-09-25T00:11:44.328087+00:00'), ('FSuoQiX8OG4KuIQ9c', '2026-09-25T00:11:44.328087+00:00')]
revenue-daily type: list len: 25
latest entry keys: ['date', 'collected_at', 'apify', 'rapidapi', 'gumroad', 'opportunities', 'warnings', 'collectors', 'revenue_estimate', 'rapidapi_paid_effect', 'apify_ppe_external_runs']
summary: {'total_triggered': 7, 'total_failed': 3, 'estimated_revenue_usd': 0.035}
triggered actors: ['japan-used-camera-market-scraper', 'japan-watch-market-scraper', 'japan-luxury-brand-market-scraper', 'japan-used-instrument-market-scraper', 'japan-offmall-market-scraper', 'mandarake-auction-scraper', 'dlsite-scraper']

# git status 確認
$ git -C /mnt/d/Project2/kensho status --porcelain -uall
M scripts/apify_ppe_external_runner.py
M kensho/scraping/collector.py
M kensho/scraping/common.py
M kensho/scraping/sources/__init__.py
M scripts/gumroad_promo_kpi.py
M scripts/gumroad_promo_weekly.py
M tests/test_gumroad_promo.py
M kensho/scraping/sources/anime_figure_api.py
M kensho/scraping/sources/anime_figure_pricing.py
M mcp/kensho-sweep-mcp/main.py
?? apify-figure-price/main.py

# mypy 確認
$ python3 -m mypy scripts/apify_ppe_external_runner.py 2>&1 | tail -5
Success: no issues found in 1 source file