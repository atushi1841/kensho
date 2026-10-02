# Outcome Review 定期再確認 2026-10-01

対象: 過去7日間（2026-09-24以降）に done になったタスク

### 事後効果測定（Outcome Review / 過去7日 done）
- KPI方向性ルール: 各 before→after の末尾に `(方向: up/down/equal)` を明記する。 この語は数値の上下のみを表し、良悪は指標の意味に依存する（例: 失敗回数・試行回数・所要秒数の down は改善 / 未pushコミット残数の up は悪化）。
- 対象: done=163件（2026-09-24以降）/ 数値KPIあり=29件
- 実測確認: あり=25件 / 未実測=4件 / KPI非該当=134件
- 実測確認率: 86.2%（目標>50%） → 達成
- 実測済みタスク:
  - `t_eb3528fb` apify-visibility-watch 連続 Request timed out 2→0 (方向: down)
  - `t_1f4779d4` pytest failed 数 10→0 (方向: down)
  - `t_f01a3a9e` stale lock 発生→自動復旧 2→0 (方向: down)
  - `t_fa77fd1e` dev.to 外部導線の発見率 0→3 (方向: up)
  - `t_f97ee44f` MCP tools live verified 0→3 (方向: up)
  - `t_866f02ae` apify_settle_rate_pct 0→0 (方向: equal), estimated_revenue_usd 0.063→0.0 (方向: down), actual_revenue_usd 0.0→0.0 (方向: equal)
  - `t_fb30f0b7` MCP ディレクトリ発見性 0→1 (方向: up)
  - `t_ceb1faef` qa_prompt_sync_pass_rate 0→100 (方向: up)
  - `t_3848cbde` 週次X販促投稿数（件/週） 0→1 (方向: up), 商品ページviews自動計測日数（日） 0→2 (方向: up)
  - `t_d5e647a1` 401/HTTP失敗時の偽成功報告率(%) 100→0 (方向: down)
- ⚠️ after<before: 8件（悪化疑い 1件 / 方向未宣言 7件）
- 悪化疑いの詳細:
  - `t_f8cec77d` 1 懸賞あたり再実行（CEILING 連続失敗）総件数 / 日 6→9 (方向: up)
  - `t_f8cec77d` goto Timeout 失敗件数 / 日（BOT シグナル代理） 3.7→7 (方向: up)
  - `t_f8cec77d` 圏外垢応募前スキップ（WiFi Disconnected 検出回数） 0→132 (方向: up)
- 方向未宣言の詳細:
  - `t_eb3528fb` apify-visibility-watch 連続 Request timed out 2→0 (方向未宣言)
  - `t_f01a3a9e` stale lock 発生→自動復旧 2→0 (方向未宣言)
  - `t_fa77fd1e` dev.to 外部導線の発見率 0→3 (方向未宣言)
  - `t_f97ee44f` MCP tools live verified 0→3 (方向未宣言)
  - `t_866f02ae` apify_settle_rate_pct 0→0 (方向未宣言)
  - `t_866f02ae` estimated_revenue_usd 0.063→0.0 (方向未宣言)
  - `t_866f02ae` actual_revenue_usd 0.0→0.0 (方向未宣言)
  - `t_fb30f0b7` MCP ディレクトリ発見性 0→1 (方向未宣言)
  - `t_ee5ca962` gumroad_sales_page_ok_fixed 0→1 (方向未宣言)
- 未実測タスク（before/after の数値を追記してクローズすること）:
  - `t_5202c42b` Apify PPE実収益化: external run決済完了監視・自動化・KPI化（kensho-revenue-worker）
  - `t_3ecce448` [収益・高] twscrape dead-skipがresearch外runでzero_streakを毎回増やし、9/2（kensho-revenue-worker）
  - `t_7d853147` [ループ衛生・計測] 失敗モード分類器の導入: MAST(14モード)をkanban失敗シグナルへ写像し dominan（kensho-worker）
  - `t_d1fee074` 再監視: 自律稼働の本番安定性7日窓を再判定（是正3件の後続）（kensho-qa）

- 検証コマンド: `grep -c "方向:" reports/outcome-review-2026-10-01.md`（≥5 で KPI方向性ルールの適用を確認）
