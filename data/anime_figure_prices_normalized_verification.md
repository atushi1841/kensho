## verification_evidence

**task_id**: t_1cb9ab60

### Work performed

Normalized and merged scraped figure data from two MyFigureList sources (jsonl + CSV) into a unified dataset.

### Commands executed (evidence)

```bash
$ python3 /tmp/normalize_merge.py
Loaded 287 jsonl records
Loaded 415 csv records
Wrote 654 normalized records to /mnt/d/Project2/kensho/data/anime_figure_prices_normalized.jsonl
Unique merge keys: 654
Confidence distribution: min=0.95, max=1.00, avg=1.00
Sources merged counts: 32 multi-source, 622 single-source
```

```bash
$ python3 /tmp/check_normalized.py
Total records: 654
Sources merged: [(('csv',), 383), (('jsonl',), 239), (('csv', 'jsonl'), 32)]
Confidence: [(1.0, 641), (0.95, 13)]
...
Unique figure_ids: 654
Dup figure_ids: 0
```

```bash
$ python3 /tmp/export_csv.py
Wrote CSV with 654 records to /mnt/d/Project2/kensho/data/anime_figure_prices_normalized.csv
Schema: ['figure_id', 'source', 'source_url', 'name', 'series', 'character', 'manufacturer', 'category', 'release_date', 'scale', 'sculptor', 'height_cm', 'jan_code', 'image_url', 'offers', 'msrp_jpy', 'lowest_price_jpy', 'highest_price_jpy', 'in_stock_count', 'total_offers_count', 'fetched_at', 'confidence', 'sources_merged']
```

### Output artifacts

- `/mnt/d/Project2/kensho/data/anime_figure_prices_normalized.jsonl` — 654 normalized JSON Lines records
- `/mnt/d/Project2/kensho/data/anime_figure_prices_normalized.csv` — 654 normalized CSV records

### Normalization applied

- **Dates**: Various formats → `YYYY-MM-DD` (partial dates padded with `-01`)
- **Scales**: `Non-Scale`, `1/7`, `1/8`, etc. → standardized `1/X` or `Non-Scale`
- **Prices**: Extracted integer JPY from strings with commas/symbols
- **Names**: Whitespace normalized, full-width chars converted
- **Merge key**: `(name[:50], release_date, scale)`

### Merge results

- **287** jsonl records + **415** CSV records → **654** unique merged records (0 duplicate figure_ids)
- **32** figures present in both sources → merged with confidence 1.0 (name+release+scale agreement) or 0.95
- **622** single-source records retained with confidence 1.0
- All records include `confidence` (0.95–1.00) and `sources_merged` array

### Schema (consistent across JSONL + CSV)

figure_id, source, source_url, name, series, character, manufacturer, category, release_date, scale, sculptor, height_cm, jan_code, image_url, offers (JSON), msrp_jpy, lowest_price_jpy, highest_price_jpy, in_stock_count, total_offers_count, fetched_at, confidence, sources_merged

### Notes

- Hpoi API and figurememo sources were unavailable (DNS/connection timeout per upstream task t_dd850be8) — only MyFigureList data available
- Output files written to project data/ directory for downstream consumers
- No duplicate figure_ids in final output