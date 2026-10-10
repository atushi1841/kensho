title: 日本市場のデータ収集を1本に詰めた85個のApify Actor — カタログ公開と使い方
tags: apify, webscraping, japan, dataengineering
published: false


# 日本市場のデータ収集を1本に詰めた85個のApify Actor — カタログ公開と使い方

日本市場のデータを自動で集めるためのApify Actorを **85個** 一気に整理しました。
すべてのActorの説明・URL・使い方を1つのカタログ（[Kensho Apps](https://atushi1841.github.io/kensho/)）にまとめました。

## このカタログでできること

- **中古市場価格**: メルカリ・ Yahooauctions・ 楽天市場・ ラクマの価格データを一括取得
- **不動産・住宅**: スモト・アパマンネット・ 村土地の価格・物件情報
- **自動車**: ゴーネットの車市場データ
- **食事**:  tabelog・ホットペッパーの飲食店データ
- **公共データ**: 天気・法務・厚生労働省・企業番号・世界銀行・ユーロスタット
- **AIエージェント連携**: MCPサーバー経由でAIから呼び出し可能なAPI

## 主なActor（85本の一部）

- [google-search-scraper](https://apify.com/fruitful_quintessence/google-search-scraper) — Google検索結果スクレイパー
- [mercari-japan-search-scraper](https://apify.com/fruitful_quintessence/mercari-japan-search-scraper) — メルカリ価格データ
- [yahoo-auctions-japan-scraper](https://apify.com/fruitful_quintessence/yahoo-auctions-japan-scraper) — Yahooauctions価格データ
- [rakuten-japan-mcp](https://apify.com/fruitful_quintessence/rakuten-japan-mcp) — 楽天市場価格API（MCP対応）
- [suumo-japan-real-estate-scraper](https://apify.com/fruitful_quintessence/suumo-japan-real-estate-scraper) — スモト不動産データ
- [japan-market-mcp](https://apify.com/fruitful_quintessence/japan-market-mcp) — 中古市場価格比較API
- [japan-fuel-price-mcp](https://apify.com/fruitful_quintessence/japan-fuel-price-mcp) — 燃料価格API
- [japan-minimum-wage-mcp](https://apify.com/fruitful_quintessence/japan-minimum-wage-mcp) — 最低賃金検索API
- [japan-anime-figure-price-data](https://apify.com/fruitful_quintessence/japan-anime-figure-price-data) — アニメフィigure中古価格
- [mlit-japan-property-prices](https://apify.com/fruitful_quintessence/mlit-japan-property-prices) — 国土交通省不動産価格
- [japan-jma-weather](https://apify.com/fruitful_quintessence/japan-jma-weather) — 気象庁天気データ
- [japan-corporate-numbers](https://apify.com/fruitful_quintessence/japan-corporate-numbers) — 企業番号データ
- [kensho-sweep-mcp](https://apify.com/fruitful_quintessence/kensho-sweep-mcp) — 懸賞・ギブ-away検索MCP

## どう使うか

Apify Storeで各Actorを検索するか、[カタログページ](https://atushi1841.github.io/kensho/)から目的のActorを選びます。
MCPサーバー対応のActorは、AIエージェント（Claude / Cursor / ChatGPT）から直接API呼び出しできます。

## データ収集の実例

中古市場の価格データを1時間で取得する場合:
1. `mercari-japan-search-scraper` でキーワード検索
2. `japan-market-mcp` で価格比較API経由で一括取得
3. `mlit-japan-property-prices` で不動産価格と組み合わせる

日本市場のデータ収集は、ApifyのActorを組み合わせることで **1本のパイプライン** にできます。
詳細は [Kensho Appsカタログ](https://atushi1841.github.io/kensho/) へ。