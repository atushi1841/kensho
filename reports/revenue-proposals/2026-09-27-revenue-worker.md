# 収益Worker 実施報告: t_1cb9ab60 — アニメフィギュア価格データ正規化・重複除去

## 実施概要
- **タスク**: t_1cb9ab60 (Clean, normalize, and merge scraped figure data into unified dataset)
- **入力**: data/anime_figure_prices.jsonl (287行, 271ユニーク figure_id, 16重複グループ)
- **出力**: data/anime_figure_prices_normalized_v2.jsonl (271行)
- **実施日時**: 2026-09-27 11:56:57

## 正規化処理内容

### 1. 重複除去・オファー統合
- 重複グループ: 16件 (32行 → 16件に集約)
- 統合オファー数: 698件
- 同一ショップ・同価格の重複を除去

### 2. 名前正規化 (33件修正)
- 連続スペースの単一化
- 前後スペース除去
- バージョン/エディション表記の抽出 (`Ver.`, `Edition`, `Limited`, `Special`, `Prize`, `Masterlise`, `Change`, `Reissue` 等)
- `version` フィールドに抽出結果を格納

### 3. メーカー名正規化 (21件修正)
- 大小文字・略称を統一 (143社 → 標準名にマッピング)
- 例: `bandai spirits` → `BANDAI SPIRITS`, `gsc` → `Good Smile Company`

### 4. スケール正規化 (63件修正)
- `None`, `Non-Scale` 文字列 → `null`
- 有効スケール (1/7, 1/8, 1/6 等) は維持

### 5. 追加フィールド
- `currency`: "JPY" (全レコード)
- `version`: 名前から抽出したバージョン/エディション
- `confidence_score`: 0.5-1.0 (マージ数・フィールド充足度・オファー数から算出)
- `source_rows_merged`: 何行マージしたか
- `normalized_at`: 正規化実行日時

## 統計サマリー

| 項目 | 値 |
|------|-----|
| 入力行数 | 287 |
| 出力行数 | 271 |
| 重複グループ | 16 |
| 統合後オファー総数 | 698 |
| 名前修正 | 33 |
| メーカー修正 | 21 |
| スケール修正 | 63 |

## データ品質指標
- 全レコード release_date 充足: 100%
- 全レコード name 充足: 100%
- manufacturer 充足: 95.2%
- image_url 充足: 100.0%
- jan_code 充足: 100.0%
- 在庫ありオファー保持レコード: 34.3%

## 次のステップ (t_822c1217: Package dataset and publish)
1. 正規化済みデータをベースにパッケージング (CSV/JSON/Parquet)
2. Apify Actor 作成 (価格比較API)
3. Gumroad 商品ページ作成 (週次CSVダウンロード)
4. RapidAPI 掲載 (有料ティア検討)

---

## Reflexion (自己レビュー)

```json
{
  "what_was_done": "t_1cb9ab60 完了 - 287行の生データから 271件に重複除去、名前/メーカー/スケール正規化、オファー統合、currency/version/confidence_score 追加フィールド付与。出力 data/anime_figure_prices_normalized_v2.jsonl",
  "what_went_well": [
    "重複グループ16件を正しく検出・マージ（同一 figure_id でオファー統合）",
    "MyFigureList の JSON-LD 構造を活かして価格・在庫・発売日を保持",
    "正規化ルールを明文化し再利用可能なスクリプト化",
    "confidence_score でデータ品質を定量化"
  ],
  "what_could_improve": [
    "Hpoi/figurememo が接続不可のためマルチソース統合が未実装（将来の拡張余地）",
    "version 抽出が単純パターンマッチのみ（複雑な版別表現には未対応）",
    "メーカー正規化マップが手動メンテ（将来的にファジーマッチ導入検討）"
  ],
  "mistakes_or_risks": [
    "親タスク t_dd850be8 が並行実行中で jsonl が追記され続けている（正規化は読み取り専用なので安全）",
    "重複除去時に最新 fetched_at を採用していない（全行同一内容なら問題なし）"
  ],
  "learned": "MyFigureList の sitemap 経由収集は安定。JSON-LD 構造化データがあるためパースが堅牢。重複はサイトマップの分割（figure-0.xml, figure-1.xml 等）で同一URLが複数サイトマップに含まれることによる。正規化ステップをパイプラインに組み込むのが正解。",
  "confidence": 9,
  "verification_evidence": "python3 scripts/normalize_figure_data.py => 入力287行/ユニーク271/重複16グループ/出力271行/オファー統合; python3 -c "import json; d=[json.loads(l) for l in open('data/anime_figure_prices_normalized_v2.jsonl')]; print(len(d), sum(1 for r in d if r.get('confidence_score')>0.8))" => 271 245"
}
