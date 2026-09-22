# Japan TCG / Pokemon Card Used-Price Dataset (駿河屋)

Japanese-language secondary-market price data for trading card games (Pokemon TCG
中心), collected from Suruga-ya (駿河屋), Japan's largest second-hand hobby retailer.
Designed for overseas Pokemon/TCG investors and resellers who need a Japan-market
price reference.

## Files

| File | Contents |
|------|----------|
| tcg_dataset_latest.csv | Current snapshot — latest observed price per item |
| tcg_price_history.csv | Time series — every price observation with `collected_at` |
| accumulated.jsonl | Append-only raw observations (JSONL) |

## Schema (CSV)

- `name` — item title (Japanese; brand/publisher in `brand`)
- `url` — canonical Suruga-ya product URL (dedupe key)
- `used_price_jpy` — current used price in JPY (primary reference price)
- `new_price_jpy` — new/sealed price in JPY when listed
- `list_price_jpy` — original list price (定価) when known
- `marketplace_price_jpy` — marketplace reseller price in JPY
- `brand` — publisher/brand when detected
- `keyword` — the search term that surfaced the item
- `in_stock` — 1/0 stock availability at collection time
- `condition_badge`, `release_date` — condition badge / release date when present
- `collected_at` — UTC timestamp of the observation (ISO 8601)

## Dataset stats (last build)

- Unique items:            125
- Total observations:      600
- Items with used price:   71
- Items in stock:          71
- Keywords:                ポケモンカードゲーム イーブイ, ポケモンカードゲーム ピカチュウ, ポケモンカードゲーム ポケモンカード151, ポケモンカードゲーム ミュウツー, ポケモンカードゲーム リザードン
- Collection window:       2026-09-21T23:13:01Z → 2026-09-22T22:30:40Z
- Used-price movers seen:  2

## Use cases

- **Export / reseller arbitrage**: find Japanese retail prices below your overseas exit price
- **Price monitoring**: track a card's used-price trend over time (see history CSV)
- **Market research**: reference Japan-market demand for a set/card before buying
- **AI training data**: labelled 125-row snapshot of JP secondary-market prices

## Data notes & license

- Source: public listing pages of suruga-ya.jp (Japan IP). Collected at low frequency with
  crawl-delay to stay within polite-use bounds. No official API exists.
- Prices are point-in-time observations captured at `collected_at`; they are indicative,
  not a live feed, and may differ from the current listing.
- **License: CC BY-SA 4.0.** Attribution required; share-alike applies. Commercial use allowed.
  This is independent data; not affiliated with or endorsed by Suruga-ya or the Pokemon Company.
- For the price-history timeline, data must be accumulated over successive runs — a single
  snapshot shows current prices only.
