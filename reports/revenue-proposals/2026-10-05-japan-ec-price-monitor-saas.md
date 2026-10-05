# 日本EC価格監視通知Micro SaaS 実装・仕様レポート (t_973250e5)

**作成日**: 2026-10-05  
**担当**: kensho-worker  
**対象タスク**: t_973250e5（価格監視通知サービス — 日本EC特化型Micro SaaS）

---

## 1. 概要とビジネスモデル

本Micro SaaSは、日本の主要ECプラットフォーム（Yahoo!ショッピング、楽天市場、メルカリ、駿河屋等）における商品の価格変動・値下がりを常時監視し、ユーザーが設定した条件（目標価格以下、値下がり検知、パーセント下落、在庫復活）を満たした瞬間にTelegram / Webhook / メールへ即時通知するサービスです。

### サブスクリプション価格プラン (MRR: 月1〜3万円目標)
| プラン名 | 月額料金 | 監視上限 | チェック頻度 | 通知チャネル | 特徴 |
|:---|:---:|:---:|:---:|:---|:---|
| **Free** | ¥0 | 3商品 | 60分 | Telegram | 無料トライアル・集客用 |
| **Pro** | ¥1,980 | 30商品 | 30分 | Telegram / Webhook | 個人せどり・人気商品監視 |
| **Business** | ¥4,980 | 200商品 | 15分 | Telegram / Webhook / メール | 法人・専門バイヤー・高頻度 |

- **MRR試算**: Pro (¥1,980) × 10〜15名 または Business (¥4,980) × 5名で **月額 20,000〜30,000円 (目標達成)**

---

## 2. システム構成と実装内容

既存の Kensho プロジェクト資産（`kensho/scraping/` のスクレイパー技術、`kensho/utils/notify.py` のTelegram通知基盤）を再利用・統合し、プロダクション品質のモジュール `kensho/price_monitor/` を実装しました。

### モジュール構成 (`kensho/price_monitor/`)
1. **`models.py`**:
   - `SubscriptionTier` (free, pro, business), `AlertCondition` (lte, percent_drop, any_drop, in_stock)
   - `PriceAlertRuleCreate`, `PriceAlertRuleUpdate`, `PriceAlertRule`
   - `PriceLogEntry`, `AlertNotificationLog`, `Subscription`
2. **`db.py` (`PriceMonitorDB`)**:
   - SQLiteを用いた永続化層（`subscriptions`, `rules`, `price_logs`, `notification_logs` テーブル）
   - プラン上限（`max_rules`, `min_interval_minutes`）の厳格な検証と制御
   - 価格履歴（`price_logs`）および通知ログ（`notification_logs`）の自動記録
3. **`scraper.py` (`ECPriceScraper`, `detect_platform`, `clean_price`)**:
   - URLからプラットフォーム（Yahoo!ショッピング、楽天市場、メルカリ、駿河屋、一般サイト）を自動識別
   - JSON-LD (Schema.org `Product`), OpenGraph メタタグ, 正規表現によるフォールバックパース
   - 在庫状態（`InStock` vs `OutOfStock` / `SOLD`）の判定
4. **`notifier.py` (`PriceNotifier`)**:
   - Telegram Bot API（`send_telegram` 連動）によるリッチなHTMLメッセージ通知
   - Webhook POST通知（システム連携・n8n・Discord等向け）
5. **`service.py` (`PriceMonitorService`)**:
   - ルール評価エンジン（条件判定、閾値チェック、差分計算）
   - 即時チェック（`check_single_rule`）およびスケジュール一括チェック（`run_due_checks`）
6. **`api.py` (FastAPI Web Application)**:
   - `/health` : ヘルスチェック
   - `/api/v1/plans` : プラン一覧
   - `/api/v1/users/{user_id}/subscription` & `/api/v1/users/subscribe` : サブスクリプション管理
   - `/api/v1/rules` (POST, GET, PATCH, DELETE) : 監視ルールCRUD
   - `/api/v1/rules/{rule_id}/check` & `/api/v1/cron/run-due-checks` : チェックトリガー
   - `/api/v1/rules/{rule_id}/history` & `/api/v1/users/{user_id}/notifications` : ログ・履歴API
7. **`worker.py` (`PriceMonitorWorker`)**:
   - 定期実行デーモン（設定インターバル毎に `run_due_checks` を自動実行）
8. **`cli.py`**:
   - CLI操作インターフェース（`serve`, `worker`, `add-rule`, `list-rules`, `check`, `subscribe`）

---

## 3. テストと動作検証

- テストスイート `tests/test_price_monitor.py` を作成し、以下を網羅:
  - プラットフォーム自動判定（Yahoo, Rakuten, Mercari, Surugaya, Generic）
  - 日本円表記パース（¥, 円, カンマ混在対応）
  - サブスクリプションプラン上限バリデーション（Free 3件、Pro 30件、Business 200件）
  - アラート条件判定（目標価格以下、下落率%下落）
  - FastAPI エンドポイント統合テスト（ヘルスチェック、ルールCRUD、手動チェック実行、履歴取得、プラン変更）
- **結果**: 5 tests passed (100% pass rate).

---

## 4. 収益化・公開ロードマップ

1. **初期集客**:
   - dev.to / note / Qiita にて「日本EC価格監視API & 通知BOTの作り方」技術記事を発行
   - X (@kensho 運用アカウント群) よりせどり・人気商品（限定フィギュア・家電）の値下がり速報デモを配信
2. **決済連携**:
   - Stripe Checkout / Gumroad サブスクリプション連携による自動有料化
3. **運用**:
   - 既存の cron / systemd ワーカー環境に `kensho.price_monitor.worker` を追加常駐
