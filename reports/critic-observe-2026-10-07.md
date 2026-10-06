# Critic 観察レポート 2026-10-07

## ループ健康度
- score: 100 / streak: 0 / priority: new_proposals（盤面空→新規提案必要）
- 盤面: ready=0 / blocked=0 / todo=0 / in_progress=0 / done=781

## 新規発見バグ: Apify外部run自動起動HTTP 400
- **スクリプト**: `scripts/apify_ppe_external_runner.py`（週1 cron 月曜4時）
- **症状**: 20 actor target中、2 actor が HTTP 400 Failure
  1. surugaya-japan-hobby-prices → `Field input.searchKeyword is required`
  2. jackroad-used-watch-scraper → `Field input.keyword is required`
- **根因**: PRIORITY_ACTORS に input_mapping キー未定義。trigger_actor_run() は常に空 payload を送信
- **追加発見**: 82 actor中 11個が input.required を要する（mercari/suumo/kakaku/hotpepper等）
- **影響**: 外部run=0/43日継続、PPE収益$0/月。2エラー×週1=毎月8回無駄実行
- **既存actorは動作中**: mandarake-auction-scraper run=SUCCEEDED（10/3・10/5）
- **提案**: t_7acf18f2（ready / assignee=kensho-revenue-worker）

## 収益状態（2026-10-04収集）
- Apify: 82本（公開78）/ 総runs 5422 / 30日ユーザー65（外部0）
- RapidAPI: 24本 / FREEMIUM 24
- Gumroad: 売上$0 / login_ok=True / state_exists=True（FILE MISSINGはCDP未実行）
- dev.to: API有効（User-Agent 追加で200 OK）。投稿3件済み
- 月間収益見込み: $0

## 監視系cron（7ジョブ error 継続、収益化無関係）
- kensho-daily-applied-recover: streak=15
- kensho-hourly-bot-safety-check: streak=16
- kensho-dataset-weekly-update: streak=3
→ 内部運用ツール。blocked_triage 対象外。

## Outcome Review 済み（過去7日 done=85件）
- 実測確認率: 83.3%（目標>50%）達成
- KPI方向性未宣言: 15件（改善予定）
- 実測タスク: t_f31ad46d / t_8dc8051f / t_d65c58ba / t_9d8430d9 / t_e2b43c47 / t_1d1323a5 など
