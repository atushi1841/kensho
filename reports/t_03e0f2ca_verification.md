# t_03e0f2ca — Verification Report

## verification_evidence
$ curl -s -o /dev/null -w "HTTP %{http_code}" https://atushi5.gumroad.com/l/agyhq
HTTP 200

$ curl -s -o /dev/null -w "HTTP %{http_code}" https://gumroad.com/l/japanese-hobby-collectibles-dataset
HTTP 404

$ python3 scripts/publish_devto.py reports/journalism/drafts/devto-2026W40-en.md --publish --public
[OK] https://dev.to/atu_ino_ed473db24d76d234a/japanese-market-data-you-can-actually-use-8-apify-actors-for-scraping-mercari-yahoo-auctions-2ehd (id=4796304)

$ python3 scripts/gumroad_promo_kpi.py
[2026-10-04 23:53:37] KPI sales_source=api sales_week=0 sales_met=False views=2(prev=2) dod=0.0%

## Summary
- Task: t_03e0f2ca
- Status: complete
- Changes:
  1. `scripts/gumroad_views_check.py` line 13 の死URL(`https://gumroad.com/l/japanese-hobby-collectibles-dataset`)を実在URL(`https://atushi5.gumroad.com/l/agyhq`)に修正 → HTTP 404 から HTTP 200 に復旧
  2. `reports/journalism/drafts/devto-2026W40-en.md` を dev.to へ公開投稿 (`id=4796304`) → 外部流入チャネルを開拓
  3. `scripts/gumroad_promo_kpi.py` で日次KPI計測を実行し、自動評価ループを維持

## Outcome
- metric: 外部流入チャネル数
- before: 0
- after: 1
