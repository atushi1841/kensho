title: 日本市場データを手に入れる8つのApify Actor ― Mercari・Yahoo!オークション・ラクマをScraping
tags:
  - Apify
  - Python
  - Web Scraping
  - Japan
  - Data
private: false

# 日本市場データを手に入れる8つのApify Actor

日本のマーケットプレイス（Mercari、Yahoo!オークション、ラクマなど）から構造化データを取得するためのApify Actor群を公開しています。

## What each actor does

| Actor | Target | What it extracts |
|-------|--------|------------------|
| mercari-japan-search-scraper | Mercari Japan | Search results, prices, listing details |
| yahoo-auctions-japan-scraper | Yahoo Auctions | Active/closed listings, bid history |
| japan-kakaku-price-search | Kakaku.com | Price comparisons across retailers |
| suumo-japan-real-estate-scraper | SUUMO | Rental/property listings |
| japan-market-mcp | Multi-platform | Unified MCP interface |
| rakuten-japan-mcp | Rakuten Market | Product catalog via MCP |
| mercari-japan-scraper | Mercari Japan | Full listing scraper |
| japan-prize-giveaway-scraper | X Giveaways | Sweepstakes campaign data |

## Why this matters

日本の市場データはAPIが限られており、構造化された情報を得るのが困難です。これらのActorはスクレイピングの複雑さを隠蔽し、リアルタイムの価格・出品データを提供します。

## Getting started

各ActorにはExample run input、Dataset output（JSON/CSV）、Scheduled runs機能が付きます。

ソース: [github.com/atushi1841/kensho](https://github.com/atushi1841/kensho)
