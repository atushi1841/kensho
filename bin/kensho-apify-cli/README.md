# kensho-apify-cli

CLI toolkit for managing and testing Apify actors from the Kensho portfolio.

## Overview

This package provides a command-line interface to interact with 86 Apify actors focused on Japanese market data (prices, auctions, e-commerce). It's designed for developers who want to quickly test these actors without navigating the Apify Console.

## Installation

```bash
pip install kensho-apify-cli
```

Or from source:
```bash
pip install -e .
```

## Prerequisites

- Python 3.10+
- Apify API token (get one at https://console.apify.com/account#/integrations)

Set your token:
```bash
export APIFY_TOKEN=your_token_here
```

## Commands

### List actors
```bash
# List all actors
kensho-apify list

# Filter by category
kensho-apify list --category manga

# Search by keyword
kensho-apify list --search camera

# Limit output
kensho-apify list --limit 10
```

### Get actor info
```bash
kensho-apify info <actor-id-or-name>
kensho-apify info surugaya-japan-hobby-prices
```

### Trigger a test run
```bash
kensho-apify run <actor-id>
kensho-apify run DKzufUSvmuXNKHeYx --timeout 300
```

### Check actor stats
```bash
kensho-apify stats <actor-id>
```

### Search actors
```bash
kensho-apify search anime
kensho-apify search camera
```

### Generate sample input data
```bash
kensho-apify seed
kensho-apify seed --output ./my-seeds
```

### Fetch fresh data from Apify
```bash
kensho-apify fetch
```

## Actor Categories

The portfolio includes actors for:
- **Anime/Manga**: Figure prices, auction data
- **Electronics**: Cameras, watches, smartphones
- **Retail**: Mercari, Yahoo Auctions, Rakuten
- **Specialty**: Fishing tackle, musical instruments, luxury brands
- **Price Comparison**: Kakaku.com, OffMall

## Example Workflow

```bash
# 1. See what's available
kensho-apify list --category camera

# 2. Get details on a specific actor
kensho-apify info japan-used-camera-market-scraper

# 3. Generate test input
kensho-apify seed

# 4. Trigger a run
kensho-apify run mQaZFo6up4YZKepC3

# 5. Check results
kensho-apify stats mQaZFo6up4YZKepC3
```

## API Endpoints Used

- `GET /v2/acts` - List actors
- `GET /v2/acts/{id}` - Get actor details
- `POST /v2/acts/{id}/runs` - Trigger a run
- `GET /v2/acts/{id}/runs` - Get run history

## License

MIT
