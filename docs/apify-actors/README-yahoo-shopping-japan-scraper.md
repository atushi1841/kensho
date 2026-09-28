# yahoo-shopping-japan-scraper

This Apify actor scrapes **Yahoo! Shopping** (shopping.yahoo.jp) product, price, and review data from Japan's largest shopping search engine. It produces structured JSON or CSV suitable for resale arbitrage, market research, price monitoring, and AI training pipelines.

## What it scrapes

For each product found, the actor extracts:

- **Title** (product name in Japanese)
- **Price** (JPY, with discount/original price distinction where available)
- **Shop** (shop name, shop ID)
- **Category** (taxonomy path)
- **Review** (rating, review count)
- **URL** (canonical product link)
- **Images** (URLs, alt text)
- **Timestamp** (when scraped)

## Input

The actor accepts the following input fields:

- `startUrls` (array): Initial listing or category URLs to seed the crawl
- `maxItems` (integer, default 1000): Maximum number of items to scrape per run
- `proxyConfiguration` (object): Proxy settings (use residential or datacenter based on target)
- `searchKeyword` (string, optional): Filter listings by keyword
- `priceRange` (object, optional): { min, max } in JPY to filter listings

## Output

Results are written to the default Apify dataset in this shape:

```json
{
  "title": "...",
  "priceJpy": 12345,
  "shop": { "name": "...", "shopId": "..." },
  "category": ["...", "..."],
  "rating": 4.5,
  "reviewCount": 128,
  "images": ["https://..."],
  "url": "https://...",
  "scrapedAt": "2026-09-05T00:00:00Z"
}
```

## Pricing

Pay-per-event: **charged per item scraped**. See the actor's pricing tab for the current per-item rate. No monthly subscription required; you pay only for what you actually collect.

## Use cases

- **Resale arbitrage**: identify underpriced listings on one marketplace to flip on another
- **Market research**: track price trends, new arrivals, and shop behaviour over time
- **Price monitoring**: alert when items cross your buy/sell thresholds
- **AI training data**: build labelled datasets for category classification, price prediction, and listing generation
- **Competitor analysis**: monitor which shops dominate which categories

## Compliance

Source listings are public; the actor respects robots.txt and includes polite crawl delays. For high-volume or commercial scraping, configure residential proxies via the input schema.

This actor is part of a suite covering major Japanese marketplaces and second-hand chains. Combine it with sibling actors (mercari-japan-search-scraper, rakuten-market-scraper, camera/watch/luxury/instrument/offmall/surugaya/komehyo/etc.) to build a unified Japan-market dataset.