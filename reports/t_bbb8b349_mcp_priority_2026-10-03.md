# MCP Connector化優先順位レポート

**タスク**: t_bbb8b349 — 残54 ActorsのMCP Connector化優先順位  
**日時**: 2026-10-03  
**実行者**: Agnes (Hermes Agent)

---

## 選定基準

1. **外部利用数**: 過去7日間の外部ユーザー・Run数
2. **総Run数**: 累計Run数（安定性指標）
3. **汎用性**: データの再利用価値（価格データ > スクレイピング結果）
4. **データ品質**: 構造化されたJSON出力、多次元時系列
5. **既存資産**: 対応するローカルデータFILEの有無

---

## 優先順位リスト（上位10本）

| 順位 | アクター名 | Run数 | ユーザー | 価格 | 理由 |
|-----|-----------|-------|---------|------|------|
| 1 | **japan-anime-figure-price-data** | 109 | 2 | $0.002 | 構造化価格データ+既存JSONL資産 |
| 2 | **mandarake-auction-scraper** | 324 | 2 | $0.35 | 高価値オークションデータ |
| 3 | **japan-offmall-market-scraper** | 312 | 2 | $0.002 | 複数店舗価格比較データ |
| 4 | **japan-kakaku-price-search** | 124 | 1 | $0.002 | 価格比較サイトデータ |
| 5 | **japan-used-camera-market-scraper** | 129 | 1 | $0.002 | キャmera価格時系列 |
| 6 | **japan-used-instrument-market-scraper** | 120 | 2 | $0.002 | 楽器価格データ |
| 7 | **japan-watch-market-scraper** | 120 | 2 | $0.002 | 時計価格データ |
| 8 | **yahoo-auctions-japan-scraper** | 119 | 2 | $0.002 | オークション履歴 |
| 9 | **japan-luxury-brand-market-scraper** | 119 | 1 | $0.002 | ブランド価格データ |
| 10 | **mercari-japan-search-scraper** | 152 | 2 | $0.002 | C2C市場データ |

---

## 実装完了（1本）

### japan-anime-figure-mcp

**選択理由**:
- 既存データ資産あり: `data/anime_figure_prices_normalized.jsonl`
- 多次元時系列価格データ（shop, price, availability）
- 泛用性高い（アニメ/フィギュアコレクション市場）
- Run数109、ユーザー2、Public

**実装内容**:
```
mcp/japan-anime-figure-mcp/
├── manifest.json        # MCPB v0.4準拠
├── README.md
├── requirements.txt     # fastmcp>=3.0.0
├── server/
│   └── server.py        # FastMCP実装（3ツール）
├── data/
│   └── anime_figure_prices_normalized.jsonl  # コピー済み
└── test_mcp.py
```

**ツール定義**:
| ツール | 説明 |
|-------|------|
| `figure_current_price(name)` | 最新価格スナップショット（JPY） |
| `figure_price_history(name, limit=50)` | 価格時系列 |
| `figure_lowest_price(name)` | 全ショップ中最安値 |

**証跡**:
- `manifest.json`: MCPB v0.4準拠、3ツール定義
- `server/server.py`: FastMCP実装、README準拠
- `test_mcp.py`: 動作検証用テスト
- Data: `anime_figure_prices_normalized.jsonl` をコピー

---

## 既存MCP実装（5本）

| ディレクトリ | 名前 | データソース |
|-------------|------|-------------|
| kensho-sweep-mcp | Japan X/Twitter Sweepstakes MCP | accumulated.jsonl |
| tcg-price-japan | Japan TCG Used-Price MCP | accumulated.jsonl |
| kensho-kaku | Kensho Ken-Kaku Sweepstakes MCP | accumulated.jsonl |
| kensho-kclub | Kensho Kenshou Club Sweepstakes MCP | accumulated.jsonl |
| kensho-kema | Kensho Kema Sweepstakes MCP | 空 |

---

## 今後実施予定（54本中残り）

1. mandarake-auction-scraper → mandarake-auction-mcp
2. japan-offmall-market-scraper → offmall-market-mcp
3. japan-kakaku-price-search → kakaku-price-mcp
4. japan-used-camera-market-scraper → used-camera-mcp
5. ...（以下同様）

---

## 制約事項

- Actor削除・archive禁止
- isPublic変更禁止（別ワーカー担当）
- description/seoTitle変更禁止（別ワーカー担当）
- 価格は既存水準（$0.002〜$0.35）を超えない

---

## 出力ファイル

- `/mnt/d/Project2/kensho/data/actor_priority_analysis_2026-10-03.json` — 全86本優先度分析
- `/mnt/d/Project2/kensho/mcp/japan-anime-figure-mcp/` — 実装済みMCPサーバー
