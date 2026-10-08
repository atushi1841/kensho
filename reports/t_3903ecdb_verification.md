# Verification evidence: t_3903ecdb — kensho-everyday dead-source false positive fix

## Root cause
critic v71 flagged kensho-everyday as dead (12-collection 0 items). QA re-check
confirmed 6 items fetched at 2026-10-08 snapshot (source_new_day.json). The
source was alive; the dead-source detection was a false positive caused by
collection timing.

## Fix applied (revert worker deletion)
1. kensho/scraping/collector.py — restored Step 2h kensho-everyday collection,
   import, and log strings (patch cancelled by re-application).
2. kensho/scraping/sources/__init__.py — restored scrape_kensho_everyday import
   and __all__ entry.
3. data/dead_source_state.json — removed dead=true / zero_streak=1000, reset
   to zero_streak=0, ever_positive=true, alerted=false.

## Verification commands (3 cited)
1. `python3 -m py_compile kensho/scraping/collector.py kensho/scraping/sources/__init__.py` — PASS (exit 0)
2. `.venv/bin/python -c "import json; d=json.load(open('data/dead_source_state.json')); ke=d['sources']['kensho-everyday']; assert 'dead' not in ke and ke['zero_streak']==0; print('OK', ke)"` — PASS
3. `grep -n "kensho-everyday" kensho/scraping/collector.py` — Step 2h block and log lines present (lines 779-784, 874, 1123)

## Evidence files
- data/status/source_new_day.json — kensho-everyday: 6 items on 2026-10-08
- data/dead_source_state.json — dead flag removed
- git commit 87a9b1f — sources/__init__.py restored
- git push OK (main -> main)
