## verification_evidence
$ bash /home/atushi/.hermes/kanban/boards/kensho-ai-team/workspaces/t_3848cbde/verify_sales.sh
0
Sat Sep 26 08:22:32 JST 2026売上確認完了
$ /mnt/d/Project2/kensho/.venv/bin/python /mnt/d/Project2/kensho/scripts/gumroad_promo_weekly.py
[2026-09-26 09:39:15] [OK] 投稿成功 tweet_id=21036455（頭8桁・t_3848cbde W39）
$ /mnt/d/Project2/kensho/.venv/bin/python /mnt/d/Project2/kensho/scripts/gumroad_promo_weekly.py
[2026-09-26 09:40:25] スキップ: 今週は投稿済み (week=2026-W39, tweet_id=21036455)
$ /mnt/c/Program\ Files/nodejs/node.exe D:\Project2\kensho\scripts\gumroad_views_collect.js 2026-09-25
VIEWS_JSON:{"from":"2026-09-25","login_ok":true,"views":1,"sales":0,"referrers":{"Direct, email, IM":1},"history_saved":true}
$ /mnt/d/Project2/kensho/.venv/bin/python /mnt/d/Project2/kensho/scripts/gumroad_promo_kpi.py
[2026-09-26 09:34:31] KPI sales_source=api sales_week=0 sales_met=False views=1(prev=1) dod=0.0% views_met=False twitter_views=None
$ /mnt/d/Project2/kensho/.venv/bin/python -m pytest tests/test_gumroad_promo.py -q
19 passed in 20.26s
$ crontab -l | grep -A3 t_3848cbde
5 9 * * * /home/atushi/.hermes/profiles/kensho-revenue-worker/scripts/gumroad_views_collect.sh > /dev/null 2>&1
15 9 * * * /home/atushi/.hermes/profiles/kensho-revenue-worker/scripts/gumroad_promo_kpi.sh > /dev/null 2>&1
40 8 * * 1 /home/atushi/.hermes/profiles/kensho-revenue-worker/scripts/gumroad_promo_weekly.sh > /dev/null 2>&1

# t_3848cbde 検証レポート — Gumroad販売ゼロ継続の販促施策自動化

## t_3848cbde 概要（実装した3本柱）
1. **views日次収集** `scripts/gumroad_views_collect.js` — Gumroadダッシュボード
   `/dashboard/sales?from=…&to=…` の統計カード（Sales/Views/Total）とReferrer表を
   CDP（Chrome headless・port 9335）で抽出し `data/gumroad_views_history.json` に日次保存。
   既存の売上収集 `gumroad_sales_collect.js`（port 9333・本番稼働）とは完全分離。
2. **週次X販促投稿** `scripts/gumroad_promo_weekly.py` — ISO週キー
   （`data/gumroad_promo_weekly_state.json`）で週次dedup、8種の文言を週番号でローテーション、
   既存実績経路 `gumroad_x_post.create_tweet`（GraphQL/curl_cffi/transaction_pairs）を再利用。
   投稿tweet_idを `data/gumroad_x_post_state.json` にも併記し、既存の日次
   `gumroad_x_xanalytics`（08:50 cron）がimpressions追跡を自動で引き継ぐ。
3. **KPI日次評価** `scripts/gumroad_promo_kpi.py` — 成功指標2つを毎日自動判定:
   - 売上: API `/v2/sales` の直近7日件数 ≥1/週
   - 訪問: views前日比 ≥+20%（`gumroad_views_history.json` から計算）
   - **失敗時代替案（カード記載）**: API応答なし → `data/gumroad_state.json`
     （既存CDPダッシュボード収集）へフォールバックしダッシュボード値で判定。
   Referrer の Twitter 経由viewsを併記し週次X販促の直接効果を可視化。

## cron（crontab追加・3エントリ）
- `5 9 * * *` views収集（前日+当日）→ `gumroad_views_collect.sh`
- `15 9 * * *` KPI評価 → `gumroad_promo_kpi.sh`
- `40 8 * * 1` 週次X販促投稿 → `gumroad_promo_weekly.sh`（ISO週dedupで再実行安全）

## 実測結果（before → after）
- 週次販促投稿の稼働: before=0件/週（9/12以降ウィンドウ外で無投稿・9/15件ログで確認）
  → after=1件/週（2026-W39 に実投稿成功、dedupによる同週再投稿0件を実証）
- 商品ページviewsの自動計測: before=0日分（計測系なし・成功指標を測れない状態）
  → after=2日分取得（2026-09-25=1 view, 2026-09-26=1 view、前日比0.0%を自動算出）
- 売上KPIの自動計測: before=人手なし → after=API優先/ダッシュボードFP付きで毎日自動
  （本日実測 sales_week=0 → 1件/週の成功指標は未達・継続計測中）

## 手順の実績
- 検証コマンド（カード記載）実測: sales件数 `0` + `Sat Sep 26 08:22:32 JST 2026売上確認完了`（rc=0）。
  APIは応答正常のため「手動ダッシュボード確認への切替」は発動せず。
- 週次投稿E2E: 実投稿成功 → 同週再実行でdedupスキップ → `gumroad_x_xanalytics.py` 実行で
  新規投稿の impressions=1 を取得（impression連携経路の実地確認）。
- views収集: ラッパー経由で前日・当日の2回実行し履歴保存を確認（cygpath誤変換を手動変換に修正）。
- テスト: `tests/test_gumroad_promo.py` 19件パス（dedup/文言/前日比/フォールバックを網羅）。
  ruff: 追加3ファイル clean。

## 残課題
- 成功指標（売上1件/週・views+20%）は事業KPIのため自動化では即時未達。cron稼働後の実測を
  `data/gumroad_promo_kpi_state.json`（履歴60件）で日次観測する。
- viewsは現状1件/日前後の低トラフィック。効果増には文言/チャネルの追加検討が要る。
