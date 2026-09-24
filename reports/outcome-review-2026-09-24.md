# Outcome Review 定期再確認 2026-09-24

対象: 過去7日間（2026-09-17以降）に done になったタスク

### 事後効果測定（Outcome Review / 過去7日 done）
- KPI方向性ルール: 各 before→after の末尾に `(方向: up/down/equal)` を明記する。 この語は数値の上下のみを表し、良悪は指標の意味に依存する（例: 失敗回数・試行回数・所要秒数の down は改善 / 未pushコミット残数の up は悪化）。
- 対象: done=130件（2026-09-17以降）/ 数値KPIあり=26件
- 実測確認: あり=18件 / 未実測=8件 / KPI非該当=104件
- 実測確認率: 69.2%（目標>50%） → 達成
- ⚠️ after<before（悪化疑い）: 10件
- 未実測タスク（before/after の数値を追記してクローズすること）:
  - `t_8e1e4934` QA: t_d5ac9f32 done_guard 準拠検証（DeepSeek鍵ローテーション）（kensho-qa）
  - `t_2dccb8b3` 全プロファイルのAPI鍵健全性を応募前に検知する監視を追加（kensho-revenue-worker）
  - `t_18ecf0a5` knshow 502 partial-degradation: port kenkaku v144 page retry（kensho-revenue-worker）
  - `t_9271d891` AIチーム検証の3層化: 構成要素・軌跡・疑似本番の自動ゲート（kensho-worker）
  - `t_f7b0d3bd` 非X応募導線(LINE/Instagram/アプリ/レシート/会員ID)の分類収集を実装し可視化（kensho-revenue-worker）
  - `t_515d0237` QA検証のSectioning化:観点別分割評価で単一パス見落とし防止（kensho-revenue-worker）
  - `t_8da22532` Apify Store SEO改善・未完了3項目（Custom icon/Categories複数選択/version更（kensho-revenue-worker）
  - `t_8bc5e2b4` 公開事業者リスト受託・初期提案セット作成(サンプル100件+3テンプレ)（kensho-revenue-worker）
- 実測済みタスク:
  - `t_1a366e78` goto failed attempt (窓08:00-12:48) 81→0 (方向: down), goto failed ページ失敗グループ (窓08:00-12:48) 27→0 (方向: down), login試行 Xにログイン確認中 (窓08:00-12:48) 41→11 (方向: down)
  - `t_02a5afc4` stop_nudge_fired_after_done_guard_blocked_kanban_complete 0→2 (方向: up)
  - `t_8946706e` self_heal attempts per session-invalid apply failure 3→1 (方向: down), apply_for_account -> _apply_impl invocations per failure 3→1 (方向: down), failure ceiling blocked after 3 consecutive hourly failures (1=yes,0=no) 0→1 (方向: up), accounts sharing one failure-ceiling counter 4→1 (方向: down), apply attempts for status=dead_proxy account 3→0 (方向: down), [SELF-HEAL] structured log lines emitted per recovery event 0→1 (方向: up), config.yaml self_healing.max_attempts 3→3 (方向: equal), tests/test_self_heal.py passing tests 18→30 (方向: up)
  - `t_5af1b5d8` 最小PATH実行の running 件数(縮退の有無) 0→3 (方向: up), 最小PATH実行 vs 通常実行の JSON diff 行数 36→0 (方向: down), bare hermes 実行呼出箇所数 6→0 (方向: down)
  - `t_25db1108` step1_elapsed_sec 345→47 (方向: down), exit_code 1→0 (方向: down)
  - `t_e67d5550` escalation create path exit code under cron minimal PATH 127→0 (方向: down), crontab-referenced scripts with bare hermes (of 20) 1→0 (方向: down), real kanban cards created during verification 0→0 (方向: equal)
  - `t_adc65737` cron comment送信失敗数 (comment failed) 54→0 (方向: down)
  - `t_5dff275b` cron相当envでの自走push成功回数(/実行) 0→2 (方向: up), index.lock 競合時の commit 失敗率 100→0 (方向: down), 未pushコミット残数 1→0 (方向: down), push失敗の理由記録率 0→100 (方向: up), github_sync 回帰テスト数 0→32 (方向: up)
  - `t_3609e866` self_heal 発動件数 (apply+collection, 7日窓) 0→36 (方向: up), HANG 検知時の自動復帰率 0→100 (方向: up), docs/daily_reports 連続 push 日数 0→2 (方向: up), github_sync 自走 push 成功率 0→0 (方向: equal), complete_watchdog リマインド送信成功率 0→0 (方向: equal), complete_watchdog 誤検知件数 54→0 (方向: down), Telegram エラー通知 送出経路の有無 0→0 (方向: equal)
  - `t_4ec92f06` agent_span 自動emit由来の spans_valid（2026-09-24） 0→4 (方向: up), pytest passed 963→988 (方向: up), kensho-kanban-sync.sh への emit 配線箇所 0→3 (方向: up)
- 悪化疑いの詳細:
  - `t_1a366e78` goto failed attempt (窓08:00-12:48) 81→0 (方向: down)
  - `t_1a366e78` goto failed ページ失敗グループ (窓08:00-12:48) 27→0 (方向: down)
  - `t_1a366e78` login試行 Xにログイン確認中 (窓08:00-12:48) 41→11 (方向: down)
  - `t_8946706e` self_heal attempts per session-invalid apply failure 3→1 (方向: down)
  - `t_8946706e` apply_for_account -> _apply_impl invocations per failure 3→1 (方向: down)
  - `t_8946706e` accounts sharing one failure-ceiling counter 4→1 (方向: down)
  - `t_8946706e` apply attempts for status=dead_proxy account 3→0 (方向: down)
  - `t_5af1b5d8` 最小PATH実行 vs 通常実行の JSON diff 行数 36→0 (方向: down)
  - `t_5af1b5d8` bare hermes 実行呼出箇所数 6→0 (方向: down)
  - `t_25db1108` step1_elapsed_sec 345→47 (方向: down)
  - `t_25db1108` exit_code 1→0 (方向: down)
  - `t_e67d5550` escalation create path exit code under cron minimal PATH 127→0 (方向: down)
  - `t_e67d5550` crontab-referenced scripts with bare hermes (of 20) 1→0 (方向: down)
  - `t_adc65737` cron comment送信失敗数 (comment failed) 54→0 (方向: down)
  - `t_5dff275b` index.lock 競合時の commit 失敗率 100→0 (方向: down)
  - `t_5dff275b` 未pushコミット残数 1→0 (方向: down)
  - `t_3609e866` complete_watchdog 誤検知件数 54→0 (方向: down)
  - `t_66c14eb4` apply 自己修復最終失敗レート（件/時間） 0.952→0.186 (方向: down)
  - `t_66c14eb4` collection 自己修復最終失敗率（収集runあたり %） 100.0→0.0 (方向: down)
  - `t_96c94435` bai全死シナリオ(5バッチ)で遮断判定後に発生した冷たい呼び出し数 2→0 (方向: down)
  - `t_96c94435` bai全死シナリオ(5バッチ)での同一プロバイダ(bai)呼び出し総数 5→3 (方向: down)

- 検証コマンド: `grep -c "方向:" reports/outcome-review-2026-09-24.md`（≥5 で KPI方向性ルールの適用を確認）
