# RapidAPI 有料プラン（3-tier）設定 検証レコード — v17-B

タスク: t_bcd0e525 (revenue-critic v17-B)
実施: 2026-09-05 JST
経路: API-direct（RapidAPI studio GraphQL, cookie認証。CDP不使用）
スクリプト: scripts/rapidapi_pricing_set.py

## 対象APIと設定結果（実測・--status で確認）

| API | visibility | Basic (/call) | Pro (/call) | Ultra (/call) |
|-----|-----------|---------------|-------------|----------------|
| japan-offmall-cn (api_3697e05e) | PRIVATE | $0.001 | $0.005 | $0.01 |
| japan-camera (api_7d2dcc27)   | PUBLIC  | $0.001 | $0.005 | $0.01 |

3 tier すべて対象単価に到達。再実行で `[unchanged]`（冪等）を確認。
- ULTRA プランは2 API とも一から createBillingPlan で作成（既存に無かったため）。
- PRO は $0.02 → $0.005 に updateBillingPlanExtended で更新。
- BASIC は MONTHLY 無料 tier だったため PERUSE $0.001 として設定。

## 実装したスクリプト機能（scripts/rapidapi_pricing_set.py）

- `--status` : 対象APIの各 tier 単価を読み取り表示
- `--set-tiers` : 3-tier 価格（Basic 0.001 / Pro 0.005 / Ultra 0.01）を冪等設定
  - BASIC/PRO 存在時 → updateBillingPlanExtended
  - ULTRA 未存在時 → createBillingPlan で作成
- `--set-price P --tier X` : 単一 tier の単価を上書き
- `--dry-run` : ペイロード構築のみ
- `--json` : cron 判定用 JSON 出力
- 冪等: 対象単価に一致する ACTIVE バージョンがあればスキップ（update が新規バージョンを生成する方式に対応）

認証: /mnt/d/Project2/goo-net-car-scraper/rapidapi_auth.json（cookie+crsf+entity-id 再利用）

## 補足

- タスク文言の「PRIVATE 2 API」に対し japan-camera は現状 PUBLIC だが、3-tier 設定自体は両方に適用済み。
- 共有ファイル scripts/rapidapi_pricing_set.py は並行ワーカー（t_60f5b5de）が同一パスを編集する collision あり（japan-used-car を追記）。本タスクは対象2 API のみ操作するため影響なし。

収益見込み: 100 calls/month × $0.001〜0.01 → $0.1〜1.0 USD/month。
