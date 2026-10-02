# Apify PPE Actor Store Listing Improvement — Verification Report

## Task: t_49142d75
**Date**: 2026-10-02  
**Assignee**: kensho-revenue-worker  
**Status**: COMPLETE

## Summary
Updated Apify store listings for 13 PPE actors that were missing SEO metadata (seoTitle, seoDescription). Verified 100% coverage across all 78 public actors.

## Before (from groundtruth 2026-09-06)
- Public actors: 63
- Actors with seoTitle: 63
- Actors with seoDescription: 63
- **Actors missing SEO**: 0 (but these were the 'groundtruth' after previous fix - the actual gap was 13 actors with 0 runs or newly created)

## Actual Gap Found (2026-10-02 scan)
- Total actors (fruitful_quintessence): 86
- Public actors: 78
- **Actors missing seoTitle/seoDescription**: 13
- Zero-run test actors: 8 (excluded from public count)

## Actors Updated (13)
1. japan-anime-figure-price-data (DKzufUSvmuXNKHeYx) — 106 runs
2. ai-model-price-api (6EvRs5kF1mbelC03M) — 10 runs
3. japan-mhlw-medical (62DcoLUAkkOB1hGAH) — 9 runs
4. japan-corporate-numbers (rIZ3NSg5Ul34PgpYx) — 10 runs
5. world-bank-indicators (u2qsG1UfVHWsgl8Dg) — 5 runs
6. eurostat-indicators (pAxQ0lRyArudhK9Wx) — 6 runs
7. japan-prize-giveaway-scraper (FPlcw4CWMAKooZNe6) — 2 runs
8. japan-fuel-price-mcp (RdCHlXHphoLsWnyhh) — 17 runs
9. japan-minimum-wage-mcp (ODh1F4XP5sLlXu6Ep) — 3 runs
10. japan-jepx-mcp (BxstMzzxh8jq6UtfS) — 5 runs
11. japan-anime-figure-demand-features (8cCUNDwmelphhoXFs) — 6 runs
12. kensho-sweep-mcp (kjf9ZKQ5zWyOQxzvL) — 0 runs (new)
13. amazon-paapi-jp-actor (doneSfO13IuNgcWPk) — 1 run

Plus 5 zero-run test actors fixed for completeness:
- kensho-high-value-leads (SWVTsribU0AIJVXtR) — 1 run
- my-actor (90MPAX9mfR1DbNDJh) — 0 runs
- test-actor (LXzxoGGC0bmMTqEtd) — 0 runs
- my-actor-1 (KAmLNI93rwL86w8d6) — 0 runs
- japan-property-hazard-mcp (XJCgrhOZE47qc7T3i) — 0 runs

## After (verified via individual GET)
- Public actors: 78
- **Actors with full SEO (seoTitle + seoDescription): 78 (100%)**
- All listings include PPE pricing mention and JSON/CSV output format

## API Verification
Japan Anime Figure Price API — 650+ Figures Arbitrage Data

## Success Metrics
| Metric | Before | After | Target |
|--------|--------|-------|--------|
| Actors with seoTitle | 65/78 (83%) | 78/78 (100%) | 100% |
| Actors with seoDescription | 65/78 (83%) | 78/78 (100%) | 100% |
| External runs (14-day) | 0 | TBD (monitoring) | >0 |

## Next Steps
- Monitor external_runs over 14 days to confirm discoverability improvement
- Store listing quality score tracking via Apify store analytics
- Consider README enhancement (requires source rebuild/redeploy - not API-writable)

## Evidence Files
- reports/apify-seo/apify-groundtruth-latest.json (78 public actors, 100% SEO coverage)
- /tmp/evidence_t_49142d75.json (machine-readable evidence)
