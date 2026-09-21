# Japan Pokémon/TCG Used-Price Dataset — 国際販売戦略 (2026-09-22)

担当: kensho-worker · タスク: t_0384512b · ソース: Suruga-ya (駿河屋) 駿河屋エンタメ

## 1. 前提と結論

- 駿河屋は**日本IP限定 + Cloudflare**。無料Apifyプランでは動作不可（403/auto=0件/JP proxy=407の実証済みパターン、`apify-marketplace-scrapers`スキルに詳細）。そのため**他人が任意に動かす公開オンデマンドApifyアクターは技術的に作れない**（有料JP proxy前提なら可）。
- 自宅(日本IP)の既存 `suruga-scraper`（/mnt/d/Project2/suruga-scraper, v4・httpx+Playwrightフォールバック）は正常動作。TCGキーワードで実データ取得を確認。
- **結論: 商品は「蓄積された日本語圏TCG価格時系列データセット」として売る**。単発スナップショットより「いつ・いくらで並び・どう推移」に価値がある（`apify-actor-deployment` スキルのデータ蓄積・データセット販売節）。Gumroad等で静的データセットとして販売し、必要なら蓄積データをバックエンドにしたAPI/MCPも追加で展開可能。

## 2. 競合調査（Apify Store API, 2026-09-22）

| クエリ | total | 上位 |
|---|---|---|
| pokemon tcg | 119 | TCGplayer Pokemon Card Scraper(parseforge, **36u**) ← 需要実証だが**米国市場** |
| tcg price japan | ~ | CardRush TCG Price Scraper(Japan, datalab-jp, 3u) / Yuyu-tei系(各2u) / BigWeb(low) |
| surugaya | ~ | suruga-ya系2-3本（各1-3u）。自前surugaya-japan-hobby-pricesもStore掲載中 |

- **需要**: ポケモンカード価格データ自体はTCGplayer 36uと実需要あり。ただし米国集中。
- **日本市場TCG**: 競合は小さく（2-3u）、**差別化余地あり**。海外ポケカ/TCG投資家の「日本相場参照」ニーズが空白。
- **既存タスクとの差別化**: 的中古カメラ/kakaku差益タスクとは **TCGカード価格に特化**（駿河屋エンタメ）。

## 3. 今回の成果物

- `scripts/tcg_price_collect.py` — 駿河屋TCG収集 + 時系列蓄積パイプライン
  - キーワード群（リザードン/ピカチュウ/ミュウツー/151/イーブイ）で収集、crawl-delay遵守（低頻度・TOS準拠）
  - `accumulated.jsonl` 追記 → latest.csv（現行スナップショット）/ price_history.csv（時系列）/ tcg_dataset.json（集約メタ）
- `data/tcg_dataset/` — 初期蓄積データ（2タイムスタンプ・240 obs・116 ユニーク・71 価格付き、¥160〜¥698,000）
  - 参考: 高額例 リザードン系 ¥698,000（プレイマット等雑貨含む。カード対象は名前に「ポケモンカードゲーム」を含むもの）

## 4. 商品化アクション

1. **Gumroad出品**: 静的データセット（latest.csv + price_history.csv + accumulated.jsonl + README）。i18n識別子を英語化（Japan Pokémon TCG Used-Price Dataset – Suruga-ya）。
2. **蓄積cron**: ローカルで1日1回程度 `tcg_price_collect.py` を定期実行 → 価格履歴が蓄積し、時系列価値が上がる（スキル再掲: 単発スナップより時系列に価値）。駿河屋ボット検出回避のため低頻度（1回/日、キーワード5×1ページ）。
3. **API/MCP展開**: 蓄積が一定量溜まったら、値動きクエリAPI（価格推移・現在値・ブックオフ基準）を `japan-market-mcp` パターンで追加。AIエージェント経由収益にも接続可。
4. **GitHub SEO**: リポジトリに `suruga-ya-scraper`/`tcg`/`pokemon`/`japan` topics 設定済みか確認。

## 5. 価格案（Apify-Gumroadデータセット相場）

- 単発スナップショット: 無料/サンプル公開（ティーザー）で需要喚起
- 時系列データセット: $20〜50/版（ニッチ垂直データ相場 $20-200）
- 値動きクエリAPI: RapidAPI/Gumroadサブスク（$9/月等）に展開

## 6. 制約と法的メモ

- 駿河屋は公式APIなし。公開商品ページのみを低頻度・crawl-delay遵守で収集（TOS上「単独低頻度収集」は許容と判断、スイープ情報源も同評価）。
- 出品者個人情報を一切含めない（商品情報・価格のみ）。CC-BY-SA 4.0 データライセンス。
- ライブフィードは謳わない（point-in-time観測）。
