# Outcome Review 定期再確認 2026-09-26

対象: 過去7日間（2026-09-19以降）に done になったタスク

### 事後効果測定（Outcome Review / 過去7日 done）
- KPI方向性ルール: 各 before→after の末尾に `(方向: up/down/equal)` を明記する。 この語は数値の上下のみを表し、良悪は指標の意味に依存する（例: 失敗回数・試行回数・所要秒数の down は改善 / 未pushコミット残数の up は悪化）。
- 対象: done=183件（2026-09-19以降）/ 数値KPIあり=49件
- 実測確認: あり=35件 / 未実測=14件 / KPI非該当=134件
- 実測確認率: 71.4%（目標>50%） → 達成
- 実測済みタスク:
  - `t_ceb1faef` qa_prompt_sync_pass_rate 0→100 (方向: up)
  - `t_3848cbde` 週次X販促投稿数（件/週） 0→1 (方向: up), 商品ページviews自動計測日数（日） 0→2 (方向: up)
  - `t_d5e647a1` 401/HTTP失敗時の偽成功報告率(%) 100→0 (方向: down)
  - `t_3dbc1fbe` 当日entryとライブgumroad_stateの乖離キー数 8→0 (方向: down)
  - `t_1ab013e8` tests/test_revenue_collect.py の V94/UnknownBilling 系の失敗数 1→0 (方向: down)
  - `t_d18ac029` invisible-playwright宣言系統数 0→4 (方向: up)
  - `t_53963f88` Gumroad Cookieファイル消失時に自動復元できるか（実測ケース数） 0→1 (方向: up)
  - `t_ee5ca962` gumroad_leg_seconds 240→42 (方向: down)
  - `t_350dc888` 契約テスト tests/test_loop_health_json_contract.py の failed 件数 1→0 (方向: down)
  - `t_5ecf88bf` crash-loopカードをparkできる検出率（閾値超過カードに対するpark実行） 0→1 (方向: up)
- ⚠️ after<before: 11件（悪化疑い 10件 / 方向未宣言 1件）
- 悪化疑いの詳細:
  - `t_d5e647a1` 401/HTTP失敗時の偽成功報告率(%) 100→0 (方向: down)
  - `t_1ab013e8` tests/test_revenue_collect.py の V94/UnknownBilling 系の失敗数 1→0 (方向: down)
  - `t_fda64102` actors_free（誤報告件数） 20→0 (方向: down)
  - `t_f8cec77d` 1 懸賞あたり再実行（CEILING 連続失敗）総件数 / 日 6→9 (方向: up)
  - `t_f8cec77d` goto Timeout 失敗件数 / 日（BOT シグナル代理） 3.7→7 (方向: up)
  - `t_f8cec77d` 圏外垢応募前スキップ（WiFi Disconnected 検出回数） 0→132 (方向: up)
  - `t_62e7242b` outcome-review レポート内の `方向:` 行数 0→33 (方向: up)
  - `t_8946706e` accounts sharing one failure-ceiling counter 4→1 (方向: down)
  - `t_5af1b5d8` 最小PATH実行 vs 通常実行の JSON diff 行数 36→0 (方向: down)
  - `t_e67d5550` crontab-referenced scripts with bare hermes (of 20) 1→0 (方向: down)
  - `t_3609e866` complete_watchdog 誤検知件数 54→0 (方向: down)
  - `t_66c14eb4` 1失敗あたり実測試行回数（回） 0→3.0 (方向: up)
  - `t_66c14eb4` BOTシグナル: goto failed 件/日 63→227 (方向: up)
  - `t_66c14eb4` BOTシグナル: ログイン試行(Xにログイン確認中) 回/日 54→108 (方向: up)
- 方向未宣言の詳細:
  - `t_66c14eb4` apply 操作開始あたり最終失敗率（%） 20.81→33.33 (方向未宣言) [after の分母は3操作開始のみで統計的意味なし。悪化方向の数値も併記 統計的意味なし(n/a)]
- 未実測タスク（before/after の数値を追記してクローズすること）:
  - `t_3ecce448` [収益・高] twscrape dead-skipがresearch外runでzero_streakを毎回増やし、9/2（kensho-revenue-worker）
  - `t_7d853147` [ループ衛生・計測] 失敗モード分類器の導入: MAST(14モード)をkanban失敗シグナルへ写像し dominan（kensho-worker）
  - `t_d1fee074` 再監視: 自律稼働の本番安定性7日窓を再判定（是正3件の後続）（kensho-qa）
  - `t_e97fd8f8` Implement critic periodic before/after KPI re‑check (past N‑（kensho-worker）
  - `t_b64c35ea` [収集] 毎時収集スロットの恒常欠落: 1runが2.5h超 → 実行時間上限(deadline)と部分保存の導入（kensho-worker）
  - `t_e1407687` 幽霊assignee検出ガード実装: ヘルパーへのassignee実在チェック追加（kensho-revenue-worker）
  - `t_8e1e4934` QA: t_d5ac9f32 done_guard 準拠検証（DeepSeek鍵ローテーション）（kensho-qa）
  - `t_2dccb8b3` 全プロファイルのAPI鍵健全性を応募前に検知する監視を追加（kensho-revenue-worker）
  - `t_18ecf0a5` knshow 502 partial-degradation: port kenkaku v144 page retry（kensho-revenue-worker）
  - `t_9271d891` AIチーム検証の3層化: 構成要素・軌跡・疑似本番の自動ゲート（kensho-worker）

- 検証コマンド: `grep -c "方向:" reports/outcome-review-2026-09-26.md`（≥5 で KPI方向性ルールの適用を確認）
