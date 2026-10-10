---
title: "Weekly Update: 650+ Anime Figure Prices Now Available Free on GitHub"
tags: [data, scraping, anime, github]
published: false
---

# Weekly Update: 650+ Anime Figure Prices Now Available Free on GitHub

Every Monday, I push a fresh snapshot of Japanese anime figure prices to [GitHub Releases](https://github.com/atushi1841/kensho/releases).

## What's in the data

655 figures, each with:
- Current lowest/highest price across 5+ Japanese retailers
- Stock availability (in/out of stock counts)
- Shop-level offer details (price, URL, condition)
- MSRP, scale, sculptor, release date

The raw CSV is ~900 KB — small enough to download in seconds, rich enough to build models on.

## Why free?

I scrape this data weekly for my own resale research. Sharing it publicly serves two purposes:

1. **Reproducibility** — others can verify my price-tracking claims
2. **Network effects** — more users = more feedback = better data quality

The **full historical dataset** (price history over months, not just current snapshot) is available on [Gumroad](https://atushi5.gumroad.com/l/agyhq) for researchers who need time-series analysis.

## Technical details

- Source: MyFigureList (primary) + secondary aggregators
- Normalization: unified schema, confidence scoring, deduplication
- Delivery: automated weekly GitHub Release via Python script + GitHub Actions
- Last updated: {{DATE}}

## How to use

```bash
# Download latest release asset
curl -L -o figure_prices.csv.gz \
  $(curl -s https://api.github.com/repos/atushi1841/kensho/releases/latest \
  | grep browser_download_url \
  | grep csv.gz \
  | cut -d\" -f4)

# Or use the API
curl -s https://api.github.com/repos/atushi1841/kensho/releases/latest \
  | jq '.assets[].browser_download_url'
```

---

*This is part of the [Kensho](https://github.com/atushi1841/kensho) project — automated Japanese marketplace price tracking.*

## Related MCP Server

For real-time data access via MCP, install the japan-anime-figure-mcp:

```bash
# Install via Smithery
npx @smithery/cli install atushi1841/japan-anime-figure-mcp --client claude
```
