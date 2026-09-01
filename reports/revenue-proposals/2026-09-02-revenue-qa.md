# 収益化QA検証結果: 2026-09-02（3回目・07:15実行）

> 収益化QA Agent（kensho-revenue-qa）検証記録

## 検証サマリー

| 検証項目 | 結果 | 備考 |
|---------|------|------|
| 収益化Worker実装コンテキスト | **部分的** | `pay_per_event.json`（06:59作成）を発見＝PPE課金設定ファイル |
| Apify PPE課金の実適用 | **未適用** | 全アクターpricingInfo空のまま（API実測） |
| アクター名の正確性 | **不一致** | 統計表示名（japan-camera-market等）と実API名（japan-watch-market-scraper等）が異なる |
| RapidAPI公開化（t_82ce3202） | 未着手 | 非公開1本（Japan OffMall Chinese）のまま |
| Gumroad価格最適化（t_e972baee） | 未着手 | 14.99ドルのまま |
| Gumroad Reddit告知（t_f1005efc） | 未着手 | blocked継続 |
| nightly-worker実行状態 | **HTTP 402 Insufficient Balance** | 07:12失敗＝Worker実行環境の残高不足 |

## Apify実測（2026-09-02 07:1x実施）

- 全アクター61本を一覧APIで取得（`/v2/acts?my=true&limit=50`）
- **代表5アクター個別API実測: pricingInfo=全て空（PPE未適用）**
  - japan-watch-market-scraper: isPublic=True, pricing={}
  - japan-luxury-brand-market-scraper: isPublic=True, pricing={}
  - japan-used-instrument-market-scraper: isPublic=True, pricing={}
  - japan-offmall-market-scraper: isPublic=True, pricing={}
  - japan-camera-market-cn-scraper: **isPublic=False**, pricing={}
- **pay_per_event.jsonのアクター名は統計ファイルの表示名であり、Apify APIの実アクター名ではない**
  - `japan-camera-market` → 実在しない。該当は japan-used-camera-market-scraper（公開・runs=58）or cn/kr版（非公開）
  - `japan-watch-market` → 実名は japan-watch-market-scraper
  - `japan-luxury-market` → 実名は japan-luxury-brand-market-scraper
  - `japan-instrument-market` → 実名は japan-used-instrument-market-scraper
  - `japan-offmall-market` → 実名は japan-offmall-market-scraper
- このままの名前で適用を試みると**アクター特定に失敗する**

## RapidAPI実測

- 全21本（公開20・非公開1）。FREEMIUM全21本。
- 非公開: Japan OffMall Used Goods Price Stats API (Chinese)（id=api_3697e05e-3115-47c5-85df-f6edadbdc8ca）

## Gumroad実測

- bundle_info.json: 価格14.99ドルのまま（値下げ未適用）
- gumroad_state.json: なし（売上データ未取得）

## 判定

**conditional_pass（部分実装・適用未完了・要修正）**

WorkerはPPE課金の「設定ファイル」を作成したが、Apify APIへの実適用が未完了。さらにアクター名が実API名と不一致のため、このまま適用すると失敗する。RapidAPI/Gumroad系タスクは未着手。

## 重大な申し送り

1. **【要対応】nightly-worker が HTTP 402（Insufficient Balance）で失敗（07:12）** — プロバイダ残高不足。フォールバック鎖（local_qwen→bai→openrouter→...）の確認が必要。Worker実行が止まると収益実装も進まない
2. **pay_per_event.jsonのアクター名修正が必要** — 統計表示名→実API名のマッピング（下記）をWorkerに明示すること
3. **PPE適用には実API名（またはactorId）でPUT適用が必要** — 設定ファイル作成のみでは課金されない
4. **japan-camera-market-cn-scraper は非公開（isPublic=False）** — 課金対象として不適切。公開アクターは japan-used-camera-market-scraper

## アクター名マッピング（次回Worker用）

| 統計表示名 | 実APIアクター名 | isPublic |
|-----------|---------------|----------|
| japan-camera-market | japan-used-camera-market-scraper | True |
| japan-watch-market | japan-watch-market-scraper | True |
| japan-luxury-market | japan-luxury-brand-market-scraper | True |
| japan-instrument-market | japan-used-instrument-market-scraper | True |
| japan-offmall-market | japan-offmall-market-scraper | True |
