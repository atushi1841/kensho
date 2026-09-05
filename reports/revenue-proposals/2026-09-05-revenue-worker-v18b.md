# Worker v18-B: Apify top5 PPE actor SEO baseline measurement (t_b6684e7b)

**担当:** kensho-revenue-worker
**日時:** 2026-09-05 03:35 JST
**ブランチ:** main
**タスク:** t_b6684e7b
**前提:** v15-A (t_90fce3df) 説明文一括テンプレーティング適用済み（baseline 2026-09-04）

---

## 概要

v15-A で適用した説明文（description / seoTitle / seoDescription）改善が
Apify Store CTR に与える影響を、PPE 課金アクター top5 について
24h / 72h / 168h 後に追跡する**測定レイヤー**を実装した。

計測対象（KEYS）:
- japan-camera-market (japan-used-camera-market-scraper)
- japan-watch-market (japan-watch-market-scraper)
- japan-luxury-market (japan-luxury-brand-market-scraper)
- japan-instrument-market (japan-used-instrument-market-scraper)
- japan-offmall-market (japan-offmall-market-scraper)

## 指標定義（重要な制限）

Apify 公開 API（v2）は **Store ページの view 数を直接公開しない**ため
（`/v2/acts/{id}/stats` 等の traffic/analytics エンドポイントは全て 404 を実測確認）、
`external_views` は **外部（owner 以外）ユーザーの累積 run 数** を proxy として定義する。

- これは Store CTR の「下方ファネル」（画面到達 → 実際に使用）を測れる唯一の公開シグナル。
- CTR の厳密な定義（インプレッションに対する画面到達）は Apify データとして取得不能。proxy である旨を metric と報告の両方に明記した。
- proxy_note を revenue-daily.json の metric 内に同梱。

補助シグナル（処置フラグ含む）: total_runs（累積） / u30d（新規流入） /
bookmarks / seo_present（テンプレーティング適用の有無）

## 実装

1. **`scripts/apify_ppe_external_views.py`**（新規）
   - KEYS レジストリ（short_name → actual_name / actor_id / 単価）
   - `--point baseline|24h|72h|168h|now`（now は実行日から自動解決）
   - Apify ライブ API から per-actor metrics 収集（actor 詳細 + runs 一覧で外部カウント）
   - `data/apify_ppe_external_views_state.json` に全ポイント時系列をマージ保存
   - `revenue-daily.json` 当日エントリへ `apify_ppe_external_views_keys` メトリクス追記
2. **`scripts/kensho_revenue_collect.py`**（拡張）
   - `attach_apify_ppe_external_views_keys(entry)` を追加。state から当日メトリクスを
     日次エントリへ添付（ネットワーク不要・純粋読み取り）。main() の集約直後に呼び出し。
3. **`tests/test_apify_ppe_external_views.py`**（新規 6 テスト、API は mock）

## 検証

```
$ python3 -m pytest tests/test_apify_ppe_external_views.py -q --no-cov
6 passed

$ python3 -m mypy scripts/apify_ppe_external_views.py tests/test_apify_ppe_external_views.py
Success: no issues found in 2 source files

$ python3 -m mypy scripts/kensho_revenue_collect.py
Success: no issues found in 1 source file
```

- 対象の unit 系（test_revenue_collect.py の main 連携以外）は全て PASS。
- ※ `test_revenue_collect.py::TestMainIntegration::test_main_no_retry_when_normal` は
  フル main()（Chrome CDP / Gumroad / Apify 実通信）を呼ぶ既存**ライブ連携テスト**で、
  本サンドボックスではネットワーク待ちで timeout。**本変更とは無関係の既存挙動**。
- 別環境起因: 全体 pytest は collection 時に `patchright` モジュール欠落で
  browser / orchestrator 系 5 ファイルが collection error（既存の venv 依存問題、本変更の責務外）。

## ライブ計測（実 API）

24h ポイント（2026-09-05、baseline 2026-09-04）:

| actor | external_views(proxy) | runs | u30d | bookmarks | SEO |
|-------|-----------------------|------|------|-----------|-----|
| japan-camera-market | 0 | 65 | 1 | 0 | ✓ |
| japan-watch-market | 0 | 58 | 1 | 0 | ✓ |
| japan-luxury-market | 0 | 57 | 1 | 0 | ✓ |
| japan-instrument-market | 0 | 58 | 1 | 0 | ✓ |
| japan-offmall-market | 0 | 134 | 1 | 0 | ✓ |
| **合計** | **0** | — | — | — | **5/5** |

- 全 5 アクターが SEO✓（説明文テンプレーティング適用済みを確認）。
- external_views = 0。これは QA v17 で確認済みの「外部トラフィック 0 件」と整合する
  **正直な baseline**（説明文改善は施されたが外部流入はまだ無い）。

## スケジュール

- 24h: 2026-09-05 → **済（本実装のライブ実行で記録）**
- 72h: 2026-09-07 → cron 登録済み（job da9a1818d65d, --point now 自動解決）
- 168h: 2026-09-11 → cron 登録済み（job 3e4918e8a412, --point now 自動解決）
  - ラッパー: `~/.hermes/profiles/kensho-revenue-worker/scripts/apify_ppe_external_views_measure.sh`
  - deliver=local（計測は state / revenue-daily.json へ永続化されるため、通知不要）

## 申し送り

- **cron 発火には Hermes gateway 起動が必要**（未起動でジョブは保存済み・未発火）。
  `hermes gateway start` を要ユーザー対応として。
- 9/11（168h）確定後、external_views の 24h/72h/168h 差分で説明文改善の外部流入効果を判定。
  0 が継続なら「Store CTR 改善には説明文以外の施策（検索語の市場選定・トラフィック誘導）が必要」という
  根本判断につながる。
- Apify に Store view が公開されたら `external_views` を真の view 数へ差し替える拡張余地を残す
  （actor ごと collect 関数の分離済み）。
