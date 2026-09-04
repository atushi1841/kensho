# Japan Used Luxury Watch Prices — Jackroad, Kitamura & Komehyo (腕時計)

Second-hand and pre-owned luxury watch price data from Japan's most trusted
dealers — **Jackroad (ジャックロード), Kitamura (キタムラ) and Komehyo
(コメ兵)**. Covers Swiss, JDM and vintage pieces for resellers and price
analysts.

## What you get

For every listing:

- Brand, model, reference and movement (e.g. Rolex, Omega, Seiko, Grand Seiko)
- **Used price (中古価格)** in JPY
- Condition grading (質ランク) with box/papers/authenticity notes
- Listing URL and scrape timestamp

## Use cases

- **Resale arbitrage / 転売** — spot price gaps between dealers
- **Cross-border sourcing** — source Japanese-market luxury watches abroad
- **Price monitoring** — daily snapshots of the used-luxury-watch market
- **Brand research** — track Rolex / Grand Seiko / Seiko resale trends

## Input

Provide one or more search keywords (brand, model, reference).
Optional: price range and sort order.

## Output

Clean JSON array of watch listings. Pay-per-event pricing — you only pay for
results you actually receive.

## Pricing

- **$0.005 / result** (Pay Per Event)
- No subscription, no monthly minimum
- Runs directly from datacenter IPs — no proxy needed

## Example output

```json
{
  "shop": "Jackroad",
  "brand": "Rolex",
  "model": "Submariner 124060",
  "priceInJpy": 1450000,
  "condition": "A",
  "url": "https://www.jackroad.co.jp/...",
  "scrapedAt": "2026-09-05T00:00:00Z"
}
```

## Notes

Coverage is limited to listings published by Jackroad, Kitamura and Komehyo.
Prices and condition grades are as listed at scrape time.
