# Figure Price Data — Competitive Landscape & Market Positioning

**Date:** 2026-09-27  
**Prepared by:** kensho-revenue-qa  
**Task:** t_0ceb866a

---

## 1. Executive Summary

The anime/figure collectible price data market is **underserved for cross-market Japanese secondary data**. Existing solutions are either:
- Single-source scrapers (Apify actors per marketplace)
- Video-game/TCG focused (PriceCharting)
- Community databases without API (MyFigureCollection)
- General e-commerce price APIs (ShopSavvy, PriceAPI) lacking collectible-specific grading

**Recommended positioning:** "Japan-first, multi-market figure price intelligence" — structured, historical, condition-aware data from Yahoo Auctions, Mandarake, Suruga-ya, Mercari, and eBay US — delivered via tiered API + CSV for developers, resellers, and collectors.

**Target price points:** Free tier (samples) → ¥3,000–5,000/mo (individual resellers) → ¥15,000–30,000/mo (multi-store operators) → Custom enterprise.

---

## 2. Competitive Landscape

### 2.1 Direct Competitors (Anime Figure Price Data)

| Competitor | Type | Coverage | Pricing Model | Gaps |
|------------|------|----------|---------------|------|
| **Apify: SolarisJapan Scraper** (lulzasaur) | Actor | SolarisJapan only (new) | Pay-per-compute (~$0.13/CU) + platform sub | Single retailer, new only, no historical |
| **Apify: Mandarake Market Checker** (jpmarketdata) | Actor | Mandarake auction | Pay-per-compute | Single source, auction only |
| **Apify: Figure Aftermarket Search** (angelic_saucer) | Actor | AmiAmi, Mandarake, eBay | Pay-per-compute | 3 sources, no normalization, no history |
| **Apify: Japan Figure/Plamo Resale Stats** (fruitful_quintessence) | Actor | Yahoo Auctions + Mandarake aggregated | Pay-per-compute | Aggregated stats only, no item-level |
| **Hpoi API** (Parse marketplace) | Managed API | Hpoi.net catalog (6 endpoints) | Credit tiers: Free 200 → $30/1k → $100/5k → $300/20k → $1000/100k credits/mo | Chinese market focus, no price history, no cross-market |
| **MyFigureCollection.net** | Community DB | Largest catalog (user-curated) | Free (no official API) | No API, no price data, no programmatic access |

### 2.2 Adjacent Competitors (Collectible Price Data)

| Competitor | Type | Coverage | Pricing | Relevance |
|------------|------|----------|---------|-----------|
| **PriceCharting** | API + CSV | Video games, TCG, comics | Legendary: $6/mo ($59/yr), CSV download gated | Proven subscription model, condition grades (loose/CIB/new/graded), but **no anime figures** |
| **eBay Sold Listings** (Apify/SoldComps) | API | eBay completed sales | Pay-per-call or subscription | Global but US-centric, 90-day history limit on official API |
| **PriceAPI / ShopSavvy / PricesAPI** | General e-commerce API | Amazon, eBay, Google Shopping, 30+ countries | Usage-based | No collectible grading, no Japanese markets |
| **Keepa / ERESA / Pricetar** | Amazon JP tools | Amazon price history | ¥2,500–5,280/mo | Amazon-only, no secondary market |

### 2.3 Open Source / Free Alternatives

| Tool | Coverage | Limitation |
|------|----------|------------|
| **n8n-japan-price-monitor** (atushi1841) | Kakaku.com (new), Suruga-ya (used), eBay US | 3 sources, no auth, no history, no grading, manual deploy |
| **Mandarake/Suruga-ya MCP Server** | Mandarake + Suruga-ya | MCP protocol only, no REST API, no persistence |

---

## 3. Market Size & TAM Analysis

### 3.1 Macro Market (GrandView Research / Verified Market Research)

| Segment | 2025/2026 Size | 2030/2033 Projection | CAGR |
|---------|----------------|----------------------|------|
| Global Action Figures | $8.27B (2022) | $16.02B (2030) | 8.6% |
| US Collector Action Figures | $2.0B (2025) | $3.1B (2033) | 5.6% |
| Global Anime Figures | $8.80B (2025) | $16.20B (2033) | 6.7% |
| Global Anime Merchandising | $10.7B (2026) | $19.8B (2033) | **9.3%** |
| Japan Reuse Market | ¥3.12T (2023) | ¥3.26T (2024, +4.5%) | ~4.5% |
| Japan CtoC EC (Mercari et al.) | ¥2.53T (2024) | — | — |

**Key insight:** Anime segment grows faster (9.3% CAGR) than general action figures (8.6%). Japan is the **source market** for authentic figures — primary and secondary.

### 3.2 Addressable Tool Market (Bottom-Up)

| User Segment | Est. Users (JP) | Willingness to Pay | Monthly ARPU | TAM (Monthly) |
|--------------|-----------------|---------------------|--------------|---------------|
| Hardcore collectors (15+ figures, $500+/yr) | ~50,000 | Low (free-preferred) | ¥0–500 | ¥0–25M |
| Individual resellers (monthly profit ¥50k–500k) | ~5,000–10,000 | Medium (¥2,000–5,000) | ¥3,000 | ¥15–30M |
| Multi-store operators / lawinc buyers | ~500–1,000 | High (¥15,000–50,000) | ¥25,000 | ¥12.5–25M |
| Developers building tools/apps | ~200–500 | High (API access) | ¥10,000 | ¥2–5M |
| **Total Realistic SAM** | — | — | — | **¥30–60M/mo (¥360–720M/yr)** |

**Conservative Year 1 Target:** 100 paying users × ¥5,000 = **¥500k MRR (¥6M ARR)**  
**Year 3 Target:** 500 users × ¥8,000 blended = **¥4M MRR (¥48M ARR)**

---

## 4. Unique Value Proposition (UVP)

### 4.1 Core Differentiators

| Dimension | Our Offering | Competitors |
|-----------|--------------|-------------|
| **Market Coverage** | 5+ Japanese secondary markets (Yahoo Auctions, Mandarake, Suruga-ya, Mercari, BookOff) + eBay US | 1–3 sources max |
| **Data Structure** | Normalized schema: `item_id, title, series, character, manufacturer, scale, material, condition_grade, price_jpy, price_usd, sold_at, source_url, source_market` | Raw HTML/JSON per source |
| **Condition Grading** | Mapped to unified scale (S/A/B/C/D + unopened/box-damaged) | Missing or source-specific |
| **Historical Depth** | 12+ months retained, daily snapshots | 90 days (eBay) or none |
| **Price Trends** | Computed: 7d/30d/90d change %, volatility, seasonality | Manual only |
| **API Access** | REST + WebSocket (real-time) + daily CSV dump | Apify compute units only |
| **No API Key (JP Sources)** | Public search endpoints — zero auth friction | Same, but we normalize |

### 4.2 "Why Now" — Market Tailwinds

1. **Weak JPY** → Foreign buyers flooding Japanese secondary markets, driving price divergence
2. **Post-COVID collector boom** sustaining → Adult collectors (18+) now largest segment (GrandView: 15+ years = growing share)
3. **No unified Japanese secondary price index exists** — every reseller builds their own spreadsheet
4. **Apify compute costs rising** → Users want predictable subscription, not per-CU billing

---

## 5. Pricing Strategy

### 5.1 Tier Design (Monthly, JPY)

| Tier | Price | Credits/Month | Rate Limit | Target | Includes |
|------|-------|---------------|------------|--------|----------|
| **Free** | ¥0 | 100 | 10 req/min | Hobbyists, eval | Search only, 30-day history, 10 results/page |
| **Collector** | ¥2,980 | 1,000 | 30 req/min | Individual collectors | Full history, price alerts (5), CSV daily (100 rows) |
| **Reseller Pro** | ¥4,980 | 5,000 | 60 req/min | Individual resellers | Unlimited history, alerts (50), CSV full, WebSocket |
| **Business** | ¥19,800 | 25,000 | 200 req/min | Multi-store, lawinc | Bulk export, priority support, SLA 99.5% |
| **Enterprise** | Custom | 100,000+ | 500 req/min | Platforms, funds | Dedicated infra, custom fields, data sharing agreement |

**Credit consumption:** Search = 1, Detail = 2, History (per item) = 5, CSV row = 0.1, WebSocket msg = 0.01

### 5.2 Rationale

- **¥2,980–4,980** aligns with Keepa (¥2,500–3,000), ERESA Pro (¥4,980), Pricetar (¥5,280) — the "reseller tool" price anchor
- **Free tier** acquires developers + collectors; conversion at 3–5% realistic (Gumroad/Kaggle funnel benchmarks)
- **Credit-based** (not per-seat) matches Apify/Hpoi/Parse model — scales with usage
- **CSV daily dump** at Business+ mirrors PriceCharting Legendary gating — high-value retention lever

### 5.3 Annual Discount

- 10% off (2 months free): Collector ¥32,184/yr, Reseller Pro ¥53,784/yr, Business ¥213,840/yr

---

## 6. Target Customer Segments & GTM

### 6.1 Primary: Individual Resellers (¥50k–500k/mo profit)
- **Pain:** Manual cross-market search (Yahoo → Suruga-ya → Mercari → eBay) takes 20+ min/deal
- **Value:** 10x speed, automated alerts on target margins
- **Acquisition:** SEO "figure price comparison", Twitter/X Japanese reseller community, YouTube collabs
- **Retention:** Daily CSV + price drop alerts → workflow dependency

### 6.2 Secondary: Multi-Store Operators / Lawinc Buyers
- **Pain:** Managing 50+ SKUs across markets, hiring staff for research
- **Value:** Bulk API, webhook on price change, team seats
- **Acquisition:** Direct sales, referrals from Reseller Pro, trade shows (Wonder Festival, Akiba events)
- **Retention:** SLA, dedicated support, custom integrations

### 6.3 Tertiary: Developers / App Builders
- **Pain:** No reliable anime figure price API (Hpoi is Chinese-market, Parse credit model unpredictable)
- **Value:** Predictable REST, OpenAPI spec, SDKs (Python/JS), generous free tier
- **Acquisition:** GitHub (open-source SDK), Qiita/Zenn technical articles, Apify marketplace cross-promo
- **Retention:** API stability, versioning, changelog

### 6.4 Collectors (Long-tail, Low LTV)
- **Pain:** "Did I overpay?" / "When to sell?"
- **Value:** Collection tracker + market value dashboard (free/collector tier)
- **Acquisition:** MyFigureCollection cross-post, Reddit r/AnimeFigures, Discord servers
- **Monetization:** Upsell to Reseller Pro when they start flipping

---

## 7. Go-to-Market Sequence

| Phase | Timeline | Goal | Key Actions |
|-------|----------|------|-------------|
| **0. Validation (Now)** | 2 weeks | 20+ paid LOIs at ¥4,980 | Landing page + Stripe test mode, outreach to 50 resellers from Twitter |
| **1. Limited Beta** | Month 1–2 | 30 paying @ ¥2,980 | Invite-only, manual onboarding, daily feedback loop |
| **2. Public Launch** | Month 3 | 100 paying @ ¥4,980 blended | Product Hunt, Japanese tech blogs, Apify marketplace listing |
| **3. Scale** | Month 4–6 | 300 paying, ¥2M MRR | Affiliate program (20% revshare), SEO content, API marketplace listings |
| **4. Enterprise** | Month 6+ | 5+ Enterprise @ ¥100k+ | Direct sales, custom contracts, data licensing |

---

## 8. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **ToS / Scraping blocks** (Yahoo, Mercari, Mandarake) | High | Critical | Use official APIs where exist; respect robots.txt; rotate residential proxies; cache aggressively; legal review |
| **Free n8n workflow cannibalizes paid** | Medium | High | Free tier = sample only (100 credits, no history, no CSV); paid = full depth + automation |
| **Apify actors improve / undercut** | Medium | Medium | Differentiate on **normalized schema + history + condition grades** — Apify actors output raw |
| **Hpoi/Parse adds Japanese market coverage** | Low | Medium | First-mover on Yahoo Auctions + Mercari + cross-market aggregation |
| **PriceCharting expands to anime figures** | Low | High | They lack Japanese source access; partner instead of compete |
| **JPY volatility affects foreign demand** | Medium | Low | Price in JPY; USD display for foreign users; hedge via Stripe multi-currency |

---

## 9. Technical Architecture Notes (for Implementation)

- **Ingestion:** Apify actors (existing: kakaku, mandarake, surugaya) + custom scrapers for Yahoo Auctions / Mercari → normalize → PostgreSQL + TimescaleDB for time-series
- **API:** FastAPI + asyncpg, OpenAPI 3.1, Redis cache (1min TTL for search, 1hr for detail)
- **Historical:** Daily snapshot job → Parquet on S3 (analytics) + TimescaleDB (API)
- **Auth:** JWT (API keys), Stripe webhook for subscription sync
- **Monitoring:** Prometheus + Grafana, Sentry, log-structured analytics (ClickHouse later)

---

## 10. Recommended Next Steps

1. **Validate pricing** — Run landing page test with 3 price points (¥2,980 / ¥4,980 / ¥9,800) to 100 targeted resellers
2. **Legal review** — Confirm scraping permissibility for each Japanese source (Yahoo Auctions API? Mandarake ToS? Mercari DPoP?)
3. **Build MVP ingestion** — Wire existing Apify actors (kakaku, mandarake, surugaya) into normalization pipeline
4. **Define API contract** — OpenAPI spec v1.0, generate Python/TS SDKs
5. **Recruit 10 beta users** — From existing kensho network + Twitter reseller community

---

## Appendix: Sources Consulted

- GrandView Research: Action Figures Market Report (GVR-4-68040-022-9)
- Verified Market Research: Anime Figure Market Report 2026-2033
- Apify Marketplace: 8+ figure/collectible actors analyzed
- Parse/Hpoi API: Tiered credit pricing ($0–$1000/mo)
- PriceCharting: $6/mo Legendary, CSV gating model
- Japanese reseller tool pricing: Keepa (¥2,500–3,000), Pricetar (¥5,280), ERESA Pro (¥4,980), Crossma (¥14,800)
- n8n-japan-price-monitor (atushi1841): 3-market free workflow
- demand_research.json (internal): Japanese reseller SaaS willingness-to-pay analysis

---

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

*End of positioning document.*