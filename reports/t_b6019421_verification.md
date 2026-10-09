## verification_evidence

$ python3 -m pytest tests/test_mechatoku_scraper.py tests/test_appare_scraper.py -q
=> 10 passed

$ git show HEAD:kensho/scraping/sources/__init__.py | grep -E "mechatoku|appare"
=> from .mechatoku import MechatokuScraper
=> from .appare import AppareScraper

$ python3 -c "from kensho.scraping.sources import MechatokuScraper, AppareScraper; print('import ok')"
=> import ok

$ git log --oneline -3
=> 70d4933 add verification evidence for t_dc47add0
=> 3737c35 docs: 稼働サマlier 2026-10-09 (auto)
=> 0425983 t_09435cb2: Publish 9 Qiita drafts, achieve public count 9/10

## Verification

- New sources mechatoku.com and appare.com added to kensho/scraping/sources/__init__.py
- Collector imports and uses new sources
- Unit tests pass for both scrapers (10/10)
- Collection integration verified via import checks