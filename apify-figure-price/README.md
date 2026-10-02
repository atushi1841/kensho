# Japan Anime Figure Price Intelligence API

**Multi-market secondary price data for 650+ anime figures** — condition grades, historical depth, normalized schema.

Sources: MyFigureList (primary). Extensible architecture for Yahoo Auctions, Mandarake, Suruga-ya, Mercari.

## Quick Start

```bash
# Install the Actor
npx @apify/apify-cli add japan-anime-figure-price-data

# Run it
npx @apify/apify-cli run japan-anime-figure-price-data --input '{
  "series": "Sword Art Online",
  "minPrice": 5000,
  "limit": 50
}'
```

## API Endpoint

The Actor runs on Apify's platform. Call it programmatically:

```python
from apify_client import ApifyClient

client = ApifyClient("YOUR_APIFY_TOKEN")
run = client.actor("DKzufUSvmuXNKHeYx").call(
    input={
        "series": "Sword Art Online",
        "minPrice": 5000,
        "limit": 50,
    }
)
dataset = client.dataset(run["defaultDatasetId"]).get_items()
```

Or via the Apify API directly:

```
POST https://api.apify.com/v2/acts/DKzufUSvmuXNKHeYx/runs
Content-Type: application/json
Authorization: Bearer <token>
```

## Input Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `figureIds` | string[] | — | Filter by MyFigureList figure IDs |
| `series` | string | — | Filter by series name (partial match) |
| `character` | string | — | Filter by character name (partial match) |
| `manufacturer` | string | — | Filter by manufacturer |
| `scale` | string | — | Filter by scale (e.g. `1/7`, `1/8`) |
| `minPrice` | integer | — | Minimum price in JPY |
| `maxPrice` | integer | — | Maximum price in JPY |
| `condition` | enum | — | `NewCondition`, `UsedCondition`, `RefurbishedCondition` |
| `inStockOnly` | boolean | false | Only items with in-stock offers |
| `includeHistory` | boolean | false | Include price history (future) |
| `limit` | integer | 100 | Max results per page |
| `offset` | integer | 0 | Pagination offset |

## Output Schema

```json
{
  "items": [
    {
      "figureId": "6525",
      "sourceUrl": "https://myfigurelist.com/figure/6525/...",
      "name": "Love Live! - Eli Ayase Swimsuit Ver. 1/7 Complete Figure",
      "series": "Love Live!",
      "character": "Eli Ayase",
      "manufacturer": "Alter",
      "category": "Scale Figure",
      "releaseDate": "2016-03-01",
      "scale": "1/7",
      "sculptor": "Teruyuki",
      "heightCm": 23,
      "janCode": "4560228204094",
      "imageUrl": "https://cdn.myfigurelist.com/...",
      "offers": [
        {
          "shopName": "Ninoma",
          "priceJpy": 12370,
          "availability": "InStock",
          "url": "https://ninoma.com/...",
          "condition": "NewCondition",
          "fetchedAt": "2026-09-27T09:59:54.536848Z"
        }
      ],
      "msrpJpy": 12800,
      "lowestPriceJpy": 11800,
      "highestPriceJpy": 19343,
      "inStockCount": 5,
      "totalOffersCount": 10,
      "confidence": 0.95,
      "sourcesMerged": ["csv", "jsonl"]
    }
  ],
  "total": 654,
  "limit": 50,
  "offset": 0
}
```

## Example Queries

**Find all in-stock 1/7 scale figures over ¥10,000:**
```
{"scale": "1/7", "minPrice": 10000, "inStockOnly": true, "limit": 100}
```

**Search by series and character:**
```
{"series": "Fate", "character": "Saber", "limit": 50}
```

**Price range scan for a specific figure:**
```
{"figureIds": ["6525"], "limit": 10}
```

## Pricing

Pay-per-event (PPE): **$0.002 per item returned**. No minimum, no subscription. A query returning 100 items costs $0.20.

## Data Freshness

Offers are fetched daily and timestamped (`fetchedAt`). The dataset is refreshed on each Actor build.

## License

MIT. Data sourced from MyFigureList (CC-BY-SA).