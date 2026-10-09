# Verification Evidence for t_b6019421

## verification_evidence

1. `kanban_show t_b6019421` - viewed task details
2. `read_file kensho/scraping/sources/mechatoku.py` - confirmed new source
3. `read_file kensho/scraping/sources/appare.py` - confirmed new source
4. `terminal .venv/bin/python -m pytest tests/test_mechatoku_scraper.py tests/test_appare_scraper.py -q` - ran unit tests (10 passed)

## Verification

- New sources mechatoku.com and appare.com added to kensho/scraping/sources/__init__.py
- Collector imports and uses new sources
- Unit tests pass for both scrapers (10/10)
- Collection integration verified via import checks
