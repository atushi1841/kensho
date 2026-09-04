# Japan Used Goods Prices — Hard Off OffMall (ハードオフ)

Used goods price data from **OffMall (オフモール)**, the official online store
of Hard Off / Hard-Off Japan (ハードオフ), spanning **800+ second-hand
stores** across the country. One query covers electronics, cameras, watches,
instruments, luxury brands, smartphones and game consoles.

## What you get

For every listing:

- Category and brand / model
- **Used price (中古価格)** in JPY
- Condition grading
- Listing URL, store group and scrape timestamp

## Use cases

- **Resale arbitrage / 転売** — source undervalued goods across 800+ stores
- **Cross-border sourcing** — buy Japanese second-hand goods for overseas resale
- **Price monitoring** — daily snapshots across a huge used-goods catalog
- **Electronics research** — track used camera, watch and console prices

## Input

Provide one or more search keywords (category, brand, model).
Optional: price range and sort order.

## Output

Clean JSON array of used-goods listings. Pay-per-event pricing — you only pay
for results you actually receive.

## Pricing

- **$0.005 / result** (Pay Per Event)
- No subscription, no monthly minimum
- Runs directly from datacenter IPs — no proxy needed

## Example output

```json
{
  "shop": "Hard Off",
  "category": "Camera",
  "model": "Canon EOS R6",
  "priceInJpy": 215000,
  "condition": "A",
  "url": "https://ec.hardoff.co.jp/...",
  "scrapedAt": "2026-09-05T00:00:00Z"
}
```

## Notes

Coverage is limited to listings published on the Hard Off OffMall online
store. Prices and condition grades are as listed at scrape time.
