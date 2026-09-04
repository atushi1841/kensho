# Japan Used Musical Instrument Prices — Digimart & Ishibashi (中古楽器)

Second-hand musical instrument price data from Japan's two largest
instrument retailers — **Digimart (島村楽器) and Ishibashi Music (石橋楽器 /
U-BOX)**. Covers guitars, basses, synthesizers and professional audio gear.

## What you get

For every listing:

- Category and brand (e.g. Fender, Gibson, Yamaha, Roland)
- **Used price (中古価格)** in JPY
- Condition grading (コンディション) and year
- Listing URL and scrape timestamp

## Use cases

- **Resale arbitrage / 転売** — spot underpriced instruments between shops
- **Cross-border sourcing** — source JDM guitars and synths abroad
- **Price monitoring** — daily snapshots of the used-instrument market
- **Vintage valuation** — track classic guitar and synth resale values

## Input

Provide one or more search keywords (model, brand, instrument type).
Optional: price range and sort order.

## Output

Clean JSON array of instrument listings. Pay-per-event pricing — you only pay
for results you actually receive.

## Pricing

- **$0.005 / result** (Pay Per Event)
- No subscription, no monthly minimum
- Runs directly from datacenter IPs — no proxy needed

## Example output

```json
{
  "shop": "Ishibashi",
  "category": "Electric Guitar",
  "model": "Fender Stratocaster",
  "priceInJpy": 128000,
  "condition": "B",
  "url": "https://www.ishibashi.co.jp/...",
  "scrapedAt": "2026-09-05T00:00:00Z"
}
```

## Notes

Coverage is limited to listings published by Digimart and Ishibashi Music.
Prices and condition grades are as listed at scrape time.
