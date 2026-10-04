# AI判断実行の検証レポート — 2026-10-03

ユーザー承認（4件の回答）にもとづき実行した Apify 系作業の、**親側での read-back 検証**結果。
子エージェント3本の自己申告を鵜呑みにせず、Apify API へ直接 GET して確認した。

## 1. 実行結果の検証（自己申告 vs 実測）

| 作業 | 子の申告 | 親の実測 | 判定 |
|---|---|---|---|
| description/seoTitle キーワード注入 | 68本PUT 200 | get_actor で modifiedAt=2026-10-03T02:06Z、保存 after と live 値が完全一致 | 一致 |
| Figure Price Actor の isPublic | 公開完走・200 | GET /acts/DKzufUSvmuXNKHeYx → isPublic=True、modifiedAt=2026-10-03T02:06:14Z | 一致 |
| PPE価格設定 | 2本成功 | pricingInfos を実測 → eventPriceUsd=0.001 / 0.002 が実入りで存在 | 一致 |
| MCP化 | 1本実装 | mcp/japan-anime-figure-mcp/{manifest.json,server/server.py,README.md,test_mcp.py,data/anime_figure_prices_normalized.jsonl} 実在 | 一致 |

子の「10件のNG」は status_code=0＝クライアント側の no-op（既に適用済み）で、HTTP失敗ではない。誤報ではない。

## 2. 検証で発見した実害と修正

### 2-1. 同一テンプレートの重複タイトル（19本 → 実際は37本）
子の投入後、seoTitle が **58本中28種類しかなく**、19本が完全同一だった。

```
19x 'Japan Japan market data Scraper — Price, Listings, JSON'   ← "Japan" が二重
 4x 'Japan watches Scraper — Price, Listings, JSON'
 3x 'Japan HotPepper Beauty Scraper — Price, Listings, JSON'
 3x 'Japan luxury brand Scraper — Price, Listings, JSON'
 3x 'Japan Hard Off OffMall Scraper — Price, Listings, JSON'
 3x 'Japan musical instruments Scraper — Price, Listings, JSON'
 2x 'Japan cameras Scraper — Price, Listings, JSON'
```

**根本原因**: scripts/apify_seo_full_apply.py:136 `build_seo_title()` が
`f"Japan {label} Scraper — Price, Listings, JSON"` を生成し、`infer_usage()` の
フォールバックが `"Japan market data"` を返すため `Japan` が二重化していた。

**修正**:
1. 全86本の seoTitle を一意な内容（サイト名＋用途＋言語接尾辞）に書き換え → **86/86 distinct を実測で確認**
2. 根本修正（class fix）: `_dedupe_adjacent()` を追加し、build_title / build_seo_title /
   build_seo_description / build_description の出力直前に適用
3. `infer_usage()` のフォールバックをアクター名由来の話題語に変更（"Japan" 始まりを返さない）
4. 回帰テスト追加: tests/test_apify_seo_full_apply_titles.py（5件 pass）

適用実績: 37本 + 10本 = **47本を PUT 200 で更新、全件 read-back 一致**。
台帳: data/apify_seo_title_fix_2026-10-03.json / apify_seo_title_fix2_2026-10-03.json /
_seo_titles_final_20261003.json

### 2-2. pricingInfos の重複追加（japan-market-mcp）
japan-market-mcp (57SNehd4cHNFyUCj3) には 2026-08-10 から PPE が既に存在しており、
今回さらに同一内容の PPE が追加されて **pricingInfos が2件**になった。

- 実測: `PUT {"pricingInfos": [<1件目のみ>]}` → **HTTP 400 `cannot-remove-pricing-info`**（read-back で2件のまま）
- 影響: 2件は同一イベント定義のため課金動作は変わらない見込み。ただし表示上の重複が残る
- 消せない（API制約）。次回 Console で人間が整理するか、放置。**API では解消不能であることを実測で確定**

## 3. 未解決・人間作業として残ったもの

| 項目 | 状態 | 人間がやること |
|---|---|---|
| PPE dataset-item 価格が未設定の3本 | fuel-price / minimum-wage は event 型のみ | Console で dataset-item 課金を追加するか要否判断 |
| isPublic=False の6本 | テスト/デバッグ用・run=0 | 削除するか放置するかの判断のみ |
| Figure Price Actor の actorDefinition | build 0.1.190 でも keys=[] | 次回ビルドで inputSchema/outputSchema が埋まるか確認（UI表示に影響の可能性） |

## verification_evidence

```
$ python3 -c "GET /v2/acts/DKzufUSvmuXNKHeYx"  → isPublic=True modifiedAt=2026-10-03T02:06:14.629Z
$ python3 -c "GET /v2/acts/57SNehd4cHNFyUCj3" → pricingInfos=2, eventPriceUsd=0.001 (実入り)
$ python3 -c "PUT /v2/acts/57SNehd4cHNFyUCj3 {'pricingInfos':[pi[0]]}" → HTTP 400 cannot-remove-pricing-info
$ python3 -c "GET /v2/acts?limit=100&my=1 全86本の seoTitle 集計" → 86/86 distinct（重複0）
$ python -m pytest tests/test_apify_seo_full_apply_titles.py -q → 5 passed
$ python -m mypy --strict scripts/apify_seo_full_apply.py → 既存2件のみ（新規エラー0）
```
