# Japan Pre-Owned Luxury Brand Prices — Komehyo, Jackroad & Brand Off (中古ブランド)

Pre-owned and second-hand luxury brand price data from Japan's top
re-sellers — **Komehyo (コメ兵), Jackroad (ジャックロード) and Brand Off
(ブランドオフ)**. Covers luxury bags, wallets, accessories and watches.

## What you get

For every listing:

- Brand and item type (e.g. Hermès, Chanel, Louis Vuitton, Goyard)
- **Used resale price (中古価格)** in JPY
- Condition grading and year / authentication status (真贋・ランク)
- Listing URL and scrape timestamp

## Use cases

- **Resale arbitrage / ブランド転売** — find underpriced luxury items
- **Cross-border sourcing** — source authenticated Japanese luxury abroad
- **Price monitoring** — daily snapshots of the luxury resale market
- **Depreciation research** — track resale value of flagship bags

## Input

Provide one or more search keywords (brand, item type, product name).
Optional: price range and sort order.

## Output

Clean JSON array of luxury listings. Pay-per-event pricing — you only pay for
results you actually receive.

## Pricing

- **$0.005 / result** (Pay Per Event)
- No subscription, no monthly minimum
- Runs directly from datacenter IPs — no proxy needed

## Example output

```json
{
  "shop": "Komehyo",
  "brand": "Hermès",
  "itemType": "Birkin 30",
  "priceInJpy": 2300000,
  "condition": "A",
  "authenticated": true,
  "url": "https://www.komehyo-online.com/...",
  "scrapedAt": "2026-09-05T00:00:00Z"
}
```

## Notes

Coverage is limited to listings published by Komehyo, Jackroad and Brand Off.
Authentication status and grades are as listed at scrape time.
