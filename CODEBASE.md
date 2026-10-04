# Kensho コードベース知識マップ（CODEBASE.md）

> 生成: 2026-09-01 | 対象: /mnt/d/Project2/kensho/kensho/ (65ファイル, 14,624行)
> 目的: Aider/TencentDBがコードベース全体を高速に把握するためのwiki。
> 哲学: 「LLMはプログラマー、wikiはコードベース」（Karpathy）

## アーキテクチャ概要

```
kensho/
├── application/   # 応募処理（ブラウザ操作・ポリシー・検証）
├── scraping/      # 収集（4ソース + twscrape + 判定）
│   └── sources/   # 個別ソース実装
├── core/          # 基盤（config/logger/notifier/cleanup/lock）
├── keepalive/     # ネットワーク監視
├── utils/         # 補助（dashboard/proxy/safety/backup）
├── tools/         # CLIツール（health_check/AI team連携）
├── orchestrator.py # 全体調整
├── daemon.py       # 常駐
└── kensho_apply_single.py / kensho_collect.py # エントリ
```

## モジュール別詳細

### `kensho/application/applier.py`（2086行）
- 役割: 応募ロジック（Like/RT/Follow/Reply）
- 主要シンボル: `_get_follow_lock`, `_set_follow_lock`, `_speed_guard_needed`, `apply_for_account`, `_is_application_complete`

### `kensho/application/browser.py`（1025行）
- 役割: Firefox起動・指紋偽装・Xログイン
- 主要シンボル: `random_viewport`, `human_like_mouse`, `_build_stealth_js`, `create_browser`, `_session_has_auth_cookies`

### `kensho/application/api_actions.py`（983行）
- 役割: X内部GraphQL API操作
- 主要シンボル: `_resolve_query_id`, `_get_query_id`, `_generate_transaction_id`, `_is_api_error`

### `kensho/scraping/collector.py`（591行）
- 役割: 懸賞URL収集（4ソース）
- 主要シンボル: `_normalize_x_url`, `_dedup_x_url_merge`, `collect`

### `kensho/orchestrator.py`（498行）
- 役割: 全体オーケストレーター
- 主要シンボル: `load_state`, `save_state`, `should_collect`, `get_pending_batches`, `_safe_step`

### `kensho/application/verifier.py`（253行）
- 役割: アクション検証（連続失敗追跡）
- 主要シンボル: `ConsecutiveFailureTracker`, `AccountHealthVerifier`, `ActionVerifier`

### `kensho/application/policy_engine.py`（139行）
- 役割: ポリシー評価（日次/時間上限・間隔）
- 主要シンボル: `RiskClass`, `PolicyDecision`, `PolicyEngine`

### `kensho/application/follow_state_manager.py`（117行）
- 役割: フォロー状態管理
- 主要シンボル: `FollowStateManager`

### `kensho/application/rate_limiter.py`（215行）
- 役割: レート制限（日次カウンター）
- 主要シンボル: `load_daily_counts`, `check_rate_limit`, `daily_total_limit_reached`

### `kensho/scraping/simple_rt_classifier.py`（214行）
- 役割: RTだけで完了するかLLM判定
- 主要シンボル: `classify_texts`, `classify_collected_items`

## 主要フロー

### 収集フロー
1. `collector.collect()` → knshow/kenshouclub/cpmeikan/chancecom 等からX URL取得
2. `_normalize_x_url()` で正規化 → `_dedup_x_url_merge()` で重複排除
3. `simple_rt_classifier.classify_collected_items()` で「RTだけで完了するか」判定

### 応募フロー
1. `orchestrator.get_pending_batches()` で対象ツイート選定
2. `policy_engine.evaluate()` でポリシー評価（日次上限・時間帯・間隔）
3. `applier.apply_for_account()` で Like/RT/Follow/Reply 実行
4. `verifier` で実行検証、`audit_ledger` でSHA256監査ログ

### 安全機構
- `rate_limiter` — 日次カウンター（フォロー120/RT80/いいね200/リプライ10）
- `crash_guard` — 異常終了検出
- `proxy_watchdog` — SOCKS5プロキシ死活監視
- `freeze_festival` — アクション規模の動的調整

## 運用ルール（AGENTS.mdから）
- アクション間隔: 12〜40秒ランダム
- 1セッション最大15件、稼働時間09:00〜23:59
- リプライは単独実行、テンプレート禁止
- アカウント別指紋偽装（WebGL/Canvas/Fonts/UA）
- 排他ロック: `collected.lock` / PIDロック

## テスト
- 51テスト全パス（pytest）、mypy strict 0 error
- 実行: `python -m pytest`（D:\Project2\kensho ルートから）

## データ商品・外部API（収益化資産・CODEBASE反映）

### Apify Store — 86 Actors (PPE課金)
- `scripts/apify_store_opportunity.py` — ストア機会分析（86本全件監査済み）
- `scripts/apify_seo_desc_repair.py` — SEOメタデータ修復（完了済み）
- `scripts/apify_make_private.py` — Private化制御（PPE維持のため未実行推奨）
- `scripts/apify_store_rank.py` — ランキング/競合監視
- `scripts/apify_console_driver.js` — Apify Console自動操作（Playwright）

### Gumroad — デジタル商品自動化
- `scripts/gumroad_views_check.py` — 商品viewスクレイピング（URL修正済み: 404→200復旧）
- `scripts/gumroad_cross_post.py` — 既存データセットのクロスポスト（dev.to等）
- `scripts/github_release_weekly.py` — 週次データセットGitHub Releases自動公開
- `.github/workflows/weekly-release.yml` — GitHub Actionsスケジュール（毎週月曜 00:00 UTC）

### MCP / Smithery レジストリ登録
- `scripts/mcp_registry_register.py` — MCP公式レジストリ登録（6 servers完了）
- `scripts/smithery_register.py` — Smithery登録（description/icon充実済み）
- `scripts/mcp_so_batch_register.py` — mcp.so一括登録パイプライン

### 外部流入チャネル自動化
- `scripts/publish_devto.py` — dev.to記事投稿（APIキー設定済み・検証済み）
- `scripts/devto_weekly_pipeline.py` — 週次SEO記事パイプライン（cron: devto-weekly-seo-post）
- `scripts/devto_internal_links.py` — 既存記事への内部リンク挿入

### 収益監視・検証
- `scripts/seo_rank_watch.py` — dev.to/Apify順位監視
- `scripts/apify_store_check.py` — Apifyストア監査（日次）
- `scripts/revenue-gap-detector.sh` — 収益ギャップ検出（外部ユーザー0日数等）
- `scripts/loop_health.sh` — AIチームループ健全性（score/blocked/escalation JSON出力）

---

## 関連ドキュメント
- `README_DATASET.md` — データセット仕様・ダウンロード・有償版案内
- `references/apify-visibility-2026.md` — 86アクター実測監査レポート（設定側完了・需要側のみ）
- `references/kanban-sync-integration.md` — AIチーム Kanban同期設計
