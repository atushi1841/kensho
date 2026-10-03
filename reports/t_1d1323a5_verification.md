## verification_evidence

### 実測証拠（タスクID: t_1d1323a5）

$ hermes cron list 2>&1 | grep -A3 "apify-external-runner-weekly"
Name:      apify-external-runner-weekly
    Schedule:  0 4 * * 1
    Repeat:    ∞
    Next run: 2026-10-05T04:00:00+09:00

$ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho_apify_external_runner_cron.sh 2>&1
[2026-10-03 20:54:24 UTC] Apify PPE external runner start — owner=VMz6nlpHoGIjTeSXS
  [SKIP] japan-used-camera-market-scraper: interval < 24h
  [SKIP] japan-watch-market-scraper: interval < 24h
  [SKIP] japan-luxury-brand-market-scraper: interval < 24h
  [SKIP] japan-used-instrument-market-scraper: interval < 24h
  [SKIP] japan-offmall-market-scraper: interval < 24h
  [FAILED] surugaya-japan-hobby-prices: HTTP 400
  [SKIP] mandarake-auction-scraper: interval < 24h
  [SKIP] tackleberry-japan-fishing-tackle-scraper: interval < 24h
  [SKIP] yahoo-auctions-japan-scraper: interval < 24h
  [SKIP] dlsite-scraper: interval < 24h
  [SKIP] dmm-scraper: interval < 24h
  [SKIP] kitamura-japan-used-camera-scraper: interval < 24h
  [FAILED] jackroad-used-watch-scraper: HTTP 400
  [SKIP] komehyo-japan-brand-scraper: interval < 24h
  [SKIP] eurostat-indicators: interval < 24h
  [SKIP] world-bank-indicators: interval < 24h
  [SKIP] goo-net-car-scraper: interval < 24h
  [SKIP] biglemon-machinery-scraper: interval < 24h
  [SKIP] digimart-japan-used-instrument-scraper: interval < 24h
  [SKIP] golfpartner-used-club-scraper: interval < 24h
✓ state 保存: /mnt/d/Project2/kensho/data/apify_ppe_external_runs_state.json
✓ revenue-daily.json に apify_ppe_external_runs 追記
=== Apify PPE External Runner Summary ===
Targeted: 20 | Triggered: 0 | Failed: 2 | Skipped: 18
Estimated revenue (if all succeed): $0.0000
EXIT_CODE=0

$ python3 -c "import json; state=json.load(open('/mnt/d/Project2/kensho/data/apify_ppe_external_runs_state.json')); print('Total triggers:', len(state['last_trigger']))"
Total triggers: 18

$ python3 -c "import json; rev=json.load(open('/mnt/d/Project2/kensho/data/revenue-daily.json')); s=rev[-1]['apify_ppe_external_runs']['summary']; print('Summary:', s)"
Summary: {'total_triggered': 0, 'total_failed': 2, 'estimated_revenue_usd': 0}

$ git -C /mnt/d/Project2/kensho log --oneline -3
3048cb0 t_1d1323a5: apify_ppe_external_runner attach_to_daily KeyError耐性強化
7ea8557 t_ab4e4024: update evidence.json sha256 after guard re-write

$ git -C /mnt/d/Project2/kensho status --porcelain -- '*.py' '*.yaml' '*.sh' '*.js'
(空 = コード未committedなし)

$ bash ~/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py t_1d1323a5 --workdir /mnt/d/Project2/kensho --write-evidence --payload-file /tmp/payload_1d1323a5.json
written: /mnt/d/Project2/kensho/reports/t_1d1323a5_evidence.json (guard j verification => pass, sha256=f91a00580dbe65472cb06a596cd52b2eb7958c020ccec2d937e434f5403adaf4)

### 変更内容
- t_1d1323a5 対応: `scripts/apify_ppe_external_runner.py` の `attach_to_daily()` 内、`r["run_id"]` / `r["error"]` / `r["triggered"]` / `r["price_usd"]` 直参照を `r.get(...)` に変更。skip/failedエントリ（キー欠落）でも KeyError が発生しないようにした。`skipped` / `reason` フィールドも追加で出力。

### 結果（t_1d1323a5）
- cron ジョブ `77895199278d`（apify-external-runner-weekly / 0 4 * * 1 / no-agent）登録完了
- 実行スクリプトが exit 0 で完了（KeyError 解消）
- state.json に18件の trigger 履歴、revenue-daily.json に apify_ppe_external_runs メトリクス追記確認
- 次回実行: 2026-10-05 04:00 JST（月曜）
- commit 3048cb0 → push 済み（remote main）

### 次回検証（t_1d1323a5 継続）
- 10/05 以降に external_runs > 0 かつ actual_revenue_usd > 0 になるか確認
- 現在は 18/20 が interval スキップ（24h経過前）、2/20 が HTTP 400 失敗。次回実行で new actors が起動可能か確認必要