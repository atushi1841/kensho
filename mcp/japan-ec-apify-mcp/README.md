# Japan EC Apify MCP Server

MCP server wrapping specific Apify actors for Japanese e-commerce data:

- Mercari Japan scraper (`fruitful_quintessence/mercari-japan-search-scraper`)
- Yahoo! Auctions Japan scraper (`fruitful_quintessence/yahoo-auctions-japan-scraper`)
- Rakuten Market scraper (`fruitful_quintessence/rakuten-market-scraper`)
- SUUMO real estate scraper (`fruitful_quintessence/suumo-japan-real-estate-scraper`)
- Kakaku.com price scraper (`fruitful_quintessence/japan-kakaku-price-search`)

Each tool accepts a `keyword` and optional `limit` parameters.

## Usage

Set `APIFY_TOKEN` environment variable with a valid Apify token.

Run with `uv run python server.py` for stdio transport (default) or `uv run python server.py --http` for HTTP.

## Tools

- `run_mercari_scraper`
- `run_yahoo_auctions_scraper`
- `run_rakuten_scraper`
- `run_suumo_scraper`
- `run_kakaku_scraper`

All return the raw Apify run object including `runId` and `status`. To get actual results, use the `get_dataset` tool from the generic `kensho-apify` MCP server with the returned `runId`.

## Notes

This server focuses on wrapping the actors; result fetching is left to the generic Apify MCP server or direct Apify API calls.

## Data Source: Apify Store & Smithery Registry

This MCP server is available on:

- **Apify Store**: [Mercari/Yahoo/Rakuten/SUU_MO/Kakaku via Apify](https://apify.com/fruitful_quintessence/acts/mercari-japan-search-scraper) — Mercari/Yahoo/Rakuten/SUU_MO/Kakaku via Apify
- **Smithery Registry**: [Install via Smithery](https://server.smithery.ai/whSePszWpMtfeLYBp) — MCP server for AI agents

Install via Smithery:
```bash
npx @smithery/cli install whSePszWpMtfeLYBp --client claude
```
