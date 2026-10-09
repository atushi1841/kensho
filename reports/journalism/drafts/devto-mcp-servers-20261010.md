---
title: "I Published 10 Free MCP Servers for Japanese Data (Prices, Sweepstakes, Fuel, TCG) — Here's the Full List"
tags:
  - mcp
  - ai
  - javascript
  - datascience
published: false
---

If you build AI agents that need **real Japanese data**, you've probably hit the same wall I did: Japanese e-commerce, price indices, government datasets, and local marketplaces are scattered across sites with no clean API. So over the past few months I built and published **10 MCP (Model Context Protocol) servers** that wrap these sources into tools any MCP client (Claude Desktop, Cursor, Cline, etc.) can call directly. All are free to connect, and the source is on GitHub.

## The list

| Server | What it gives your agent | Smithery | GitHub |
|---|---|---|---|
| japan-ec-mcp | Japanese e-commerce product/price lookups (Mercari, Rakuten, Yahoo! Auctions) | [connect](https://server.smithery.ai/atushi1841/japan-ec-mcp) | [repo](https://github.com/atushi1841/japan-ec-mcp) |
| japan-market-mcp | Japanese market & price-index snapshots | [connect](https://server.smithery.ai/atushi1841/japan-market-mcp) | [repo](https://github.com/atushi1841/japan-market-mcp) |
| japan-fuel-price-mcp | Weekly official fuel prices across Japan | [connect](https://server.smithery.ai/atushi1841/japan-fuel-price-mcp) | [repo](https://github.com/atushi1841/japan-fuel-price-mcp) |
| tcg-price-japan | Trading-card (Pokemon etc.) prices from Japanese markets | [connect](https://server.smithery.ai/atushi1841/tcg-price-japan) | [repo](https://github.com/atushi1841/tcg-price-japan) |
| japan-anime-figure-mcp | Anime figure prices & availability in Japan | [connect](https://server.smithery.ai/atushi1841/japan-anime-figure-mcp) | [repo](https://github.com/atushi1841/japan-anime-figure-mcp) |
| kensho-sweep-mcp | Live Japanese sweepstakes/giveaway listings (X-based) | [connect](https://server.smithery.ai/atushi1841/kensho-sweep-mcp) | [repo](https://github.com/atushi1841/kensho-sweep-mcp) |
| kensho-kclub | Sweepstakes aggregator data (kenshou.club) | [connect](https://server.smithery.ai/atushi1841/kensho-kclub) | [repo](https://github.com/atushi1841/kensho-kclub) |
| kensho-kema | Sweepstakes aggregator data (ken-kaku / ke-ma sources) | [connect](https://server.smithery.ai/atushi1841/kensho-kema) | [repo](https://github.com/atushi1841/kensho-kema) |
| kensho-kaku | Kakaku.com-style price comparison data | [connect](https://server.smithery.ai/atushi1841/kensho-kaku) | [repo](https://github.com/atushi1841/kensho-kaku) |
| japan-ec-apify-mcp | EC data routed through managed Apify actors (no scraping setup) | [connect](https://server.smithery.ai/atushi1841/japan-ec-apify-mcp) | [repo](https://github.com/atushi1841/japan-ec-mcp) |

## Official MCP Registry entry

One of them — **mlit-property-prices-mcp** — is also published on the [official MCP Registry](https://registry.modelcontextprotocol.io) as `io.github.atushi1841/mlit-property-prices-mcp` (status: active). It exposes Japan's MLIT land-transaction price dataset (XIT001) — the actual recorded sale prices of real estate parcels — which is otherwise painful to query programmatically. If you're building anything real-estate or investment related for the Japanese market, this is the primary-source data behind the headlines.

## How to connect

Every server is hosted on Smithery, so connecting is one URL:

```json
{
  "mcpServers": {
    "japan-ec-mcp": {
      "command": "npx",
      "args": ["-y", "@smithery/cli@latest", "run", "atushi1841/japan-ec-mcp"]
    }
  }
}
```

Or just open the Smithery page for any server above and copy its connection snippet into Claude Desktop / Cursor config.

## Why I built these

I run a personal automation project around Japanese sweepstakes and price monitoring, and every data source I needed was HTML-only. Rather than one-off scrapers, I packaged each domain as an MCP server so my agents (and eventually yours) can call them as plain tools. The code is on GitHub under the `atushi1841` namespace — MIT-style, no API keys required for the free endpoints.

## What I'd like feedback on

- Which data domain would be most useful as a hosted MCP tool? (EC prices, government datasets, and sweepstakes are the current three families.)
- Are there MCP clients where Smithery-hosted servers fail to connect cleanly? I want to fix transport issues.

If any of these save you a scraping weekend, a bookmark or a star on the repo genuinely helps these show up for other people building Japan-facing agents.
