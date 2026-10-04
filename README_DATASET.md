# Anime Figure Price Dataset

> Live, normalized price data for 650+ Japanese anime figures — updated weekly via GitHub Releases.

## Download

Latest release: **[GitHub Releases](https://github.com/atushi1841/kensho/releases)**

Each weekly release contains:
- `anime_figure_prices_weekly/YYYY-Www.csv.gz` — compressed CSV (≈900 KB)

## Schema

| Column | Description |
|--------|-------------|
| `figure_id` | MyFigureList internal ID |
| `name` | Figure name |
| `series` | Anime/game series |
| `character` | Character name |
| `manufacturer` | Maker (Alter, Good Smile, etc.) |
| `release_date` | Commercial release date (YYYY-MM-DD) |
| `scale` | Scale ratio (1/7, 1/8, Non-Scale) |
| `msrp_jpy` | Manufacturer suggested retail price (¥) |
| `lowest_price_jpy` | Current lowest listed price (¥) |
| `highest_price_jpy` | Current highest listed price (¥) |
| `in_stock_count` | Number of shops with stock |
| `offers` | JSON array of shop offers (price, URL, availability) |
| `fetched_at` | Timestamp of last price fetch |
| `confidence` | Merge confidence (0.95–1.0) |
| `sources_merged` | Which sources contributed (csv, jsonl) |

## Paid version with historical data

The weekly GitHub release contains **current snapshot only**. For **historical price tracking** (date-stamped prices going back months), see:

👉 **[Anime Figure Price Dataset on Gumroad](https://atushi5.gumroad.com/l/agyhq)**

The paid version includes:
- Full price history per figure (date × price × shop)
- CSV + JSONL export
- Updated monthly
- Direct API access for researchers

## Who is this for

- **Data scientists** building price prediction models
- **Resellers** tracking market trends
- **Researchers** studying anime merch economics
- **AI agents** needing structured figure data

## License

Data provided "as-is" for personal/research use. Commercial redistribution requires separate license — contact via Gumroad.

---

*Auto-generated weekly. Source: MyFigureList + secondary aggregators.*
