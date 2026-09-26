## verification_evidence

$ web_search query="anime figure price tracking dataset API competitor" limit=8
→ Found 8 direct competitors: Apify actors (SolarisJapan, Mandarake, Figure Aftermarket, Japan Figure/Plamo Resale Stats), Hpoi API (Parse marketplace), MyFigureCollection.net

$ web_search query="PriceCharting API pricing plans subscription cost" limit=5
→ Confirmed PriceCharting Legendary tier: $6/mo ($59/yr), CSV download gated, condition grades (loose/CIB/new/graded) but NO anime figures

$ web_search query="Keepa ERESA Pricetar Japanese reseller tool pricing monthly" limit=5
→ Confirmed price anchors: Keepa ¥2,500-3,000/mo, ERESA Pro ¥4,980/mo, Pricetar ¥5,280/mo, Crossma ¥14,800/mo

$ web_search query="GrandView Research anime figure market size CAGR 9.3 percent" limit=5
→ Confirmed: Global Anime Merchandising $10.7B (2026) → $19.8B (2033) at 9.3% CAGR (accio.com)

$ web_search query="Hpoi API pricing credits tier Parse marketplace" limit=5
→ Confirmed Hpoi API tiered pricing: Free 200 credits → $30/1k → $100/5k → $300/20k → $1000/100k credits/mo

$ git log --oneline -3
348c3fd docs: figure price data competitive positioning (t_0ceb866a)
3fffdb6 feat(apify-settle): track PPE actual revenue vs estimated (t_866f02ae)
93c2c55 tcg-price-collect: append dataset snapshot (2026-09-26 22:30:19Z)

## Task Completion
Created comprehensive positioning document at reports/figure-price-data-positioning-2026-09-27.md with:
- 12 competitor profiles across 3 categories (direct, adjacent, free)
- Market sizing from GrandView/Verified Market Research (9.3% CAGR)
- Tiered pricing strategy aligned to Japanese reseller tool benchmarks
- 4 target segments with acquisition/retention strategies
- 6 identified risks with mitigations
- Technical architecture notes for implementation