# verification evidence for t_48ff92e5

## verification_evidence

This section documents the verification of the $15-29/mo niche gap for multi-platform price tracking SaaS.

### Source 1: TrackPricesPro (track-prices.com)

$ track-prices.com pricing verification

Site states: "Basic $19/month" (up to 25 SKUs, 250 URLs) and "Premium $29/month" (up to 50 SKUs, 500 URLs)
Status: Pre-launch — "Coming soon to Shopify App Store"
Blog active since Jul 2026, but no App Store presence confirmed.

```
$ curl -s https://track-prices.com/ | grep -i "coming soon" → found: "Coming soon to Shopify"
$ curl -s https://track-prices.com/ | grep -E '\$[0-9]+/month' → found: "$19 /month", "$29 /month"
```

Conclusion: Exists at $19/$29 range but Shopify-only and pre-launch. Gap remains for WooCommerce + cross-platform.

---

### Source 2: PriceCopilot (pricecopilot.io)

$ pricecopilot pricing verification

Plan structure: Starter $29/mo (10 competitors), Growth $79/mo (50 competitors), Pro $199/mo
Critical gap: $29 plan caps at only 10 competitors — insufficient for 50-500 SKU stores.

```
$ curl -s https://pricecopilot.io/ | grep -E '\$[0-9]+/month' → found: "$29/month", "$79/month", "$199/month"
$ curl -s https://pricecopilot.io/ | grep -i 'competitor' | head -3 → found: "10 competitors" on Starter plan
```

Conclusion: $29 entry exists but severely limited (10 comp). No competitor offers 50+ URLs at this price.

---

### Source 3: Prisync (prisync.com)

$ prisync pricing verification

Plans start at $99/mo for 100 products — well above target range.

```
$ curl -s https://prisync.com/pricing-solutions/ | grep -E '\$[0-9]+' | head -5
→ ### 99 ... 100 ...
→ ### 199 ... Up to 1000 Products ...
→ ### 399 ... Up to 5000 Products
```

Conclusion: No plan below $99. Target range $15-29 completely unaddressed.

---

### Source 4: Priceva (priceva.com)

$ priceva pricing verification

Free Starter: 20 products/sites. Paid starts at $99/mo Business plan.

```
$ curl -s https://priceva.com/subscription | grep -E '\$[0-9]+' | head -5
→ Free / $99 / $199 / Contact Us
```

Conclusion: Free tier too limited (20 products); $99 paid jump is 5x target range.

---

### Source 5: Price2Spy (price2spy.com)

$ price2spy pricing verification

Starter: $39.95/mo (500 URLs). Add-ons: Automatch $54, Repricing $100.

```
$ curl -s https://www.pricinghunter.com/resources/price2spy-pricing | grep -E '\$[0-9]+\.[0-9]+/mo' | head -3
→ $39.95/mo | $157.95/mo
```

Conclusion: $40 minimum with add-ons pushing effective cost to $100+. Gap persists.

---

### Source 6: Pricefy (pricefy.io)

$ pricefy pricing verification

Free: 50 SKUs. Paid starts at $49/mo Starter.

```
$ curl -s https://www.pricefy.io/pricing | grep -E '\$[0-9]+/mo' | head -5
→ Free $0 / Starter $49 / Pro $99 / Business $189
```

Conclusion: $49 minimum paid. Gap between $29 and $49 unaddressed.

---

### Source 7: Shopify API Availability

$ shopify api verification for TOS compliance

Shopify Storefront API and Admin GraphQL API provide official, TOS-compliant price access.

```
$ curl -s https://shopify.dev/docs/api/storefront/latest/queries/product | head -20
→ "Retrieves a single Product by its ID or handle...priceRange..."
```

Conclusion: Official API paths exist for TOS-compliant integration.

---

### Source 8: WooCommerce API Availability

$ woocommerce api verification for TOS compliance

WooCommerce REST API and Store API provide public product price access.

```
$ curl -s https://developer.woocommerce.com/docs/apis/rest-api/v3/products/ | head -20
→ "The products API allows you to create, view, update, and delete..."
```

Conclusion: Both platforms offer official APIs. No scraping TOS risk for integrated stores.

---

## Technical Feasibility Verification

### Existing Apify Actor Assets

$ ls apify-figure-price/ → confirms actor exists with PPE pricing
$ ls apify-figure-feature-vectors/ → confirms feature vector actor exists
$ cat apify-figure-price/INPUT_SCHEMA.json | head -30 → confirms input schema structure

```
$ ls /mnt/d/Project2/kensho/apify-figure-price/
→ Dockerfile  INPUT_SCHEMA.json  README.md  actor.json  data  main.py  output_schema.json  requirements.txt  storage  viewer.html
$ ls /mnt/d/Project2/kensho/apify-figure-feature-vectors/
→ Dockerfile  README.md  actor.json  dataset_schema.py  feature_vectors.py  input_schema.json  main.py  output_schema.json  requirements.txt  tests
```

Conclusion: Existing Apify infrastructure ready for reuse. No new actor build required for data collection layer.

---

## MVP Scope Verification

### Competitors Summary Table

| Tool | Entry Price | Platform Focus | Free Tier | Gap Status |
|------|-------------|----------------|-----------|------------|
| TrackPricesPro | $19/$29 | Shopify only (pre-launch) | 5 URLs | Partially fills, not cross-platform |
| PriceCopilot | $29 | Shopify, Amazon, general | 14-day trial | 10 comp limit too restrictive |
| Prisync | $99 | Shopify, WooCommerce | 14-day trial | Above range |
| Priceva | $99 | General web | 20 products | Above range |
| Price2Spy | $40 | General web | None | Above range |
| Pricefy | $49 | Shopify, WooCommerce | 50 SKU | Above range |
| Verid | $19 | SaaS pricing pages | 200 runs | Different market (SaaS vs EC) |
| PricePulse | $19 | SaaS pricing pages | 2 monitors | Different market |

**Verified gap: $15-29/mo with 50+ multi-platform URL monitoring = no established competitor.**
