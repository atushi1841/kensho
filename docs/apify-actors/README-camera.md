# Japan Used Camera Prices — Kitamura, Fujiya & Map Camera (中古カメラ)

Second-hand camera price data straight from Japan's leading used-camera
retailers — **Kitamura (キタムラ), Fujiya Camera (フジヤカメラ) and Map
Camera (マップカメラ)**. Built for resellers, price-monitoring dashboards and
market analysts researching the Japanese used-camera market.

## What you get

For every listing:

- Shop, brand, model and series
- **Used price (中古価格)** in JPY
- Body / lens condition grade (ランク)
- Listing URL and scrape timestamp

## Use cases

- **Resale arbitrage / 転売** — find underpriced cameras across shops
- **Cross-border sourcing** — source JDM used cameras for overseas resale
- **Price monitoring** — track depreciation and daily market moves
- **Competitive research** — compare Kitamura vs Fujiya vs Map Camera pricing

## Input

Provide one or more search keywords (model names, brands, lens types).
Optional: price range and sort order.

## Output

Clean JSON array of camera listings. Pay-per-event pricing — you only pay for
results you actually receive.

## Pricing

- **$0.005 / result** (Pay Per Event)
- No subscription, no monthly minimum
- Runs directly from datacenter IPs — no proxy needed

## Example output

```json
{
  "shop": "Kitamura",
  "brand": "Sony",
  "model": "A7 III",
  "priceInJpy": 178000,
  "condition": "A",
  "url": "https://www.kitamura.jp/shop/...",
  "scrapedAt": "2026-09-05T00:00:00Z"
}
```

## Notes

Coverage is limited to Kitamura, Fujiya Camera and Map Camera listings.
Condition grades and prices are exactly as listed on each shop's site at
scrape time.
