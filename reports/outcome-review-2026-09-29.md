# Outcome Review 定期再確認 2026-09-29

対象: 過去7日間（2026-09-22以降）に done になったタスク

### 事後効果測定（Outcome Review / 過去7日 done）
- KPI方向性ルール: 各 before→after の末尾に `(方向: up/down/equal)` を明記する。 この語は数値の上下のみを表し、良悪は指標の意味に依存する（例: 失敗回数・試行回数・所要秒数の down は改善 / 未pushコミット残数の up は悪化）。
- 対象: done=200件（2026-09-22以降）/ 数値KPIあり=49件
- 実測確認: あり=39件 / 未実測=10件 / KPI非該当=151件
- 実測確認率: 79.6%（目標>50%） → 達成
- 実測済みタスク:
  - `t_fa77fd1e` dev.to 外部導線の発見率 0→3 (方向: up)
  - `t_f97ee44f` MCP tools live verified 0→3 (方向: up)
  - `t_866f02ae` apify_settle_rate_pct 0→0 (方向: equal), estimated_revenue_usd 0.063→0.0 (方向: down), actual_revenue_usd 0.0→0.0 (方向: equal)
  - `t_fb30f0b7` MCP ディレクトリ発見性 0→1 (方向: up)
  - `t_ceb1faef` qa_prompt_sync_pass_rate 0→100 (方向: up)
  - `t_3848cbde` 週次X販促投稿数（件/週） 0→1 (方向: up), 商品ページviews自動計測日数（日） 0→2 (方向: up)
  - `t_d5e647a1` 401/HTTP失敗時の偽成功報告率(%) 100→0 (方向: down)
  - `t_3dbc1fbe` 当日entryとライブgumroad_stateの乖離キー数 8→0 (方向: down)
  - `t_1ab013e8` tests/test_revenue_collect.py の V94/UnknownBilling 系の失敗数 1→0 (方向: down)
  - `t_d18ac029` invisible-playwright宣言系統数 0→4 (方向: up)
- ⚠️ after<before: 10件（悪化疑い 3件 / 方向未宣言 7件）
- 悪化疑いの詳細:
  - `t_f8cec77d` 1 懸賞あたり再実行（CEILING 連続失敗）総件数 / 日 6→9 (方向: up)
  - `t_f8cec77d` goto Timeout 失敗件数 / 日（BOT シグナル代理） 3.7→7 (方向: up)
  - `t_f8cec77d` 圏外垢応募前スキップ（WiFi Disconnected 検出回数） 0→132 (方向: up)
  - `t_5af1b5d8` 最小PATH実行の running 件数(縮退の有無) 0→3 (方向: up)
  - `t_5af1b5d8` bare hermes 実行呼出箇所数 6→0 (方向: down)
  - `t_66c14eb4` self_heal 最終失敗の可観測件数（ログ復元、件） 0→36 (方向: up)
  - `t_66c14eb4` 1失敗あたり実測試行回数（回） 0→3.0 (方向: up)
  - `t_66c14eb4` BOTシグナル: goto failed 件/日 63→227 (方向: up)
  - `t_66c14eb4` BOTシグナル: ログイン試行(Xにログイン確認中) 回/日 54→108 (方向: up)
- 方向未宣言の詳細:
  - `t_fa77fd1e` dev.to 外部導線の発見率 0→3 (方向未宣言)
  - `t_f97ee44f` MCP tools live verified 0→3 (方向未宣言)
  - `t_866f02ae` apify_settle_rate_pct 0→0 (方向未宣言)
  - `t_866f02ae` estimated_revenue_usd 0.063→0.0 (方向未宣言)
  - `t_866f02ae` actual_revenue_usd 0.0→0.0 (方向未宣言)
  - `t_fb30f0b7` MCP ディレクトリ発見性 0→1 (方向未宣言)
  - `t_ee5ca962` gumroad_sales_page_ok_fixed 0→1 (方向未宣言)
  - `t_e67d5550` real kanban cards created during verification 0→0 (方向未宣言)
  - `t_66c14eb4` apply 操作開始あたり最終失敗率（%） 20.81→33.33 (方向未宣言) [after の分母は3操作開始のみで統計的意味なし。悪化方向の数値も併記 統計的意味なし(n/a)]
- 未実測タスク（before/after の数値を追記してクローズすること）:
  - `t_acab9ce3` Apify PPE external run 決済完了(settle)自動検知＋実収益KPI化（）
  - `t_5202c42b` Apify PPE実収益化: external run決済完了監視・自動化・KPI化（kensho-revenue-worker）
  - `t_3ecce448` [収益・高] twscrape dead-skipがresearch外runでzero_streakを毎回増やし、9/2（kensho-revenue-worker）
  - `t_7d853147` [ループ衛生・計測] 失敗モード分類器の導入: MAST(14モード)をkanban失敗シグナルへ写像し dominan（kensho-worker）
  - `t_d1fee074` 再監視: 自律稼働の本番安定性7日窓を再判定（是正3件の後続）（kensho-qa）
  - `t_e97fd8f8` Implement critic periodic before/after KPI re‑check (past N‑（kensho-worker）
  - `t_b64c35ea` [収集] 毎時収集スロットの恒常欠落: 1runが2.5h超 → 実行時間上限(deadline)と部分保存の導入（kensho-worker）
  - `t_e1407687` 幽霊assignee検出ガード実装: ヘルパーへのassignee実在チェック追加（kensho-revenue-worker）
  - `t_8e1e4934` QA: t_d5ac9f32 done_guard 準拠検証（DeepSeek鍵ローテーション）（kensho-qa）
  - `t_2dccb8b3` 全プロファイルのAPI鍵健全性を応募前に検知する監視を追加（kensho-revenue-worker）

- 検証コマンド: `grep -c "方向:" reports/outcome-review-2026-09-29.md`（≥5 で KPI方向性ルールの適用を確認）
