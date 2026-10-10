---
title: MCPサーバーで日本の中古ECデータをAIエージェントから呼び出す方法
tags: mcp, apify, japan, mercari, yahoo-auction, rakuten, ai-agent
published: false
---

# MCPサーバーで日本の中古ECデータをAIエージェントから呼び出す方法

日本の中古EC市場（メルカリ、ヤフオク、楽天、駿河屋など）の価格・在庫データは、AIエージェントがリアルタイムで意思決定する上で極めて貴重です。しかし、各プラットフォームごとに異なるAPIやスクレイピングのハードルがあり、統一的に取得するのは困難です。

そこで登場するのが **MCPサーバー（Model Context Protocol Server）** です。MCPサーバーは、標準化されたプロトコルを通じてAIエージェントとデータソースを結びつけ、複雑な統合作業を不要にします。

本記事では、kenshoプロジェクトで公開している3つのMCPサーバーを紹介し、それぞれが対応するApify Actorとの連携方法を解説します。

## 紹介するMCPサーバー

1. **japan-ec-mcp**  
   日本の主要マーケットプレース（メルカリ、ヤフオク、駿河屋、楽天、価格.com）の価格・在庫・動向を横断検索します。  
   対応Apify Actor: `mandarake-surugaya-mcp`（駿河屋価格データ）等

2. **japan-anime-figure-mcp**  
   アニメフィギュアの価格履歴と最安値情報を提供します（MyFigureList等のデータを基盤）。  
   対応Apify Actor: `japan-anime-figure-price-data`

3. **japan-market-mcp**  
   中古品全般を対象とした価格比較サーバーで、オフモール（ハードオフ官方）やカメラ、楽器、腕時計などの専門ショップをカバーします。  
   対応Apify Actor: `japan-market-mcp`自身が複数のActorをラップ

## 使い方例（Claude Desktop / Cursor）

```bash
# MCPサーバーをインストール（例: japan-ec-mcp）
npx -y mcpb fetch io.github.atushi1841/japan-ec-mcp@0.1.0 --transport stdio

# それからMCP設定ファイルに追加
# {
#   "mcpServers": {
#     "japan-ec-mcp": {
#       "command": "npx",
#       "args": ["-y", "mcpb", "fetch", "io.github.atushi1841/japan-ec-mcp@0.1.0", "--transport", "stdio"]
#     }
#   }
# }
```

Apify Storeへのリンクは記事末尾に自動追加されます。

## 期待できる効果

- AIエージェントから日本の中古ECデータへの統一インターフェース
- スクレイピングのメンテナンスコスト削減
- データ取得の信頼性向上（公式API・正規ルートを利用）

## Smithery インストール

```bash
# japan-ec-mcp をインストール
npx @smithery/cli install atushi1841/japan-ec-mcp --client claude
```

---

---

## Data used in this post

- [mercari-japan-search-scraper](https://apify.com/fruitful_quintessence/mercari-japan-search-scraper)
