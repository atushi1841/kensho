---
title: MLIT Japan Property Prices — Free Data for AI Agents & Real Estate Investors
tags: data, japan, api, real-estate
published: false
---

# MLIT Japan Property Prices — Free Data for AI Agents & Real Estate Investors

Japan's Ministry of Land, Infrastructure, Transport and Tourism (MLIT) publishes detailed real estate transaction prices for all 47 prefectures — but accessing this data programmatically has always been clunky.

I've built an open tool that makes it trivially easy for AI agents and investors to query this data.

## What's in the data

- **47 prefectures** with transaction price records
- **Q3 2005 onwards** — over a decade of historical data
- Fields include: price (yen), land area, location (city/ward), building info, zoning classification
- Clean JSON output via API

The raw data comes from MLIT's Reinfolib system (XIT001 dataset), which I've wrapped in an Apify actor for easy programmatic access.

## Two ways to access it

### Option 1: Apify Actor (API-friendly)

Query transaction prices directly via the Apify API:

```bash
# Example: get recent transactions in Tokyo
curl https://api.apify.com/v2/acts/fruitful_quintessence~mlit-japan-property-prices/runs?token=YOUR_APIFY_TOKEN

# Or run via the web UI:
# https://apify.com/fruitful_quintessence/mlit-japan-property-prices
```

The actor is free to try (pay-per-result pricing at $0.005 per record). No credit card required for the free tier.

**Store link**: https://apify.com/fruitful_quintessence/mlit-japan-property-prices

### Option 2: MCP Server (for AI agents)

If you're using Claude, Cursor, or any MCP-compatible agent, install with:

```bash
# Install the MCP server
npx -y mcpb fetch io.github.atushi1841/mlit-property-prices-mcp@0.1.0 --transport stdio

# Then add to your MCP config
```

The MCP server exposes tools like `get_property_prices` that let your AI agent query MLIT data directly in natural language.

**MCP registry**: https://www.modelcontextprotocol.io/registry

## Why this matters

Property price data is critical for:
- Real estate investment analysis
- Market trend visualization
- AI-powered valuation models
- Competitive pricing research

Until now, scraping MLIT's Reinfolib required handling Japanese government PDFs and complex web forms. This actor does the hard part so you can focus on analysis.

## Use cases I've tested

1. **Automated price tracking** — monitor specific areas for price movements
2. **Investment screening** — filter by price per square meter across regions
3. **AI agent research** — let Claude/Cursor query current market prices in real-time
4. **Data journalism** — build maps and charts of Japanese real estate trends

## Getting started

1. **Try it free**: Sign up at https://apify.com (free tier includes 100 GB storage, 100 min/month compute)
2. **Run a test**: https://apify.com/fruitful_quintessence/mlit-japan-property-prices/actions/run
3. **Integrate**: Use the API token to query programmatically, or add the MCP server to your agent config

## About the data source

MLIT (国土交通省) is Japan's equivalent of the Department of Land, Infrastructure and Transport. Their Reinfolib system (https://www.reinkan.org/) publishes standardized transaction prices for all residential property sales recorded by local municipalities. This is the most comprehensive official property price database in Japan.

I've been automating Japanese market data collection for months — from anime figures to auction prices to now, real estate. The goal is making Japanese market data accessible to global developers and investors.

## What's next

I'm building similar actors for:
- Prefecture-level price indices (not just individual transactions)
- Time-series export (CSV/JSON history)
- Map visualization (GIS coordinates)

If you find this useful or have specific data needs, let me know in the comments.

---

## Data used in this post

The dataset behind this post is available on Apify (pay-per-result, free tier to start):

- [mlit-japan-property-prices](https://apify.com/fruitful_quintessence/mlit-japan-property-prices)

## Smithery MCP Server

For AI agents using MCP-compatible tools (Claude, Cursor, VS Code), install directly:

```bash
# Install MLIT Property Prices MCP via Smithery
npx @smithery/cli install atushi1841/mlit-property-prices-mcp --client claude
```
