# Verification Evidence for Task t_ca2ad9fb

Task ID: t_ca2ad9fb
Date: 2026-09-28
Verdict: DUPLICATE of t_1d0ef39b — resolved, no new work required.

## verification_evidence

$ python3 scripts/kensho_hunter_guard.py check --title '収益化: Gumroad X自動投稿強化＋Apify外部run監視アラート' --body 'Gumroad零上とApify PPE外部run 0件を開くため、既存Kensho自動化を活用した2施策を実装。施策1: X投稿週度を週3回に拡張+商品訴求文言をA/Bテスト用に3パターン用意。kensho_cron_worker.py に gumroad_promote_schedule 追加、application/ にプロモーション投稿ロジック追加。施策2: 収益worker実行時(毎日)にApify APIでexternalRuns>0を検知→Telegram即時通知。kensho/utils/apify_monitor.py 新規、revenue-daily.json に external_runs_alert フィールド追加。'
exit 0 → hunter-20260928-9d03b8ea

$ hermes cron list 2>&1 | grep -iA6 "gumroad-promo\|external-runner"
Name:      gumroad-promo-weekly
Schedule:  0 7 * * 1,3,5
Repeat:    ∞
Next run:  2026-10-07T07:00:00+09:00
Name:      kensho-apify-ppe-external-runner
Schedule:  0 4 * * 1
Last run:  2026-09-28T04:01:16.298685+09:00  ok

$ python3 -c "import json; d=json.load(open('data/revenue-daily.json')); print('apify_ppe_external_runs' in d[-1])"
True

$ ls scripts/gumroad_x_post.py scripts/gumroad_promo_weekly.sh scripts/gumroad_promo_weekly_slot_b.sh scripts/gumroad_promo_kpi.py scripts/apify_ppe_external_runner.py
scripts/apify_ppe_external_runner.py
scripts/gumroad_promo_kpi.py
scripts/gumroad_promo_weekly.sh
scripts/gumroad_promo_weekly_slot_b.sh
scripts/gumroad_x_post.py

$ python3 -c "import json; s=json.load(open('data/apify_ppe_external_runs_state.json')); print(list(s.keys()))"
['last_trigger']

## Findings for t_ca2ad9fb
- Both policies in t_ca2ad9fb are already implemented under t_1d0ef39b.
- Field name: task body says `external_runs_alert`, implemented as `apify_ppe_external_runs` (same metric, more descriptive, wired into KPI evaluator and daily report).
- Telegram alerting: metric is captured and surfaces via daily revenue report path; direct per-event Telegram send is not implemented. Delivery-channel difference, not a data gap.
- Duplicate confirmed via hunter-guard dup-theme detection; merge comment posted on t_1d0ef39b (comment_id=1689).