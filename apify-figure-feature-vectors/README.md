# Japan Anime Figure Demand Feature Vectors

**Fixed-dimension (48), normalized feature vectors for 650+ Japan anime/figure SKUs** — purpose-built for AI agents, ML training pipelines and quant research.

Derived from the multi-shop price snapshot published by
[`japan-anime-figure-price-data`](https://apify.com/atushi/japan-anime-figure-price-data).
No scraping happens at run time: this Actor re-projects an already-collected
dataset into a machine-consumable feature matrix.

> **What this is not:** it is not a back-tested price forecast. See
> [Limitations](#limitations) before you build on it.

---

## Quick start

```bash
npx @apify/apify-cli run atushi/japan-anime-figure-demand-features --input '{
  "hasPriceOnly": true,
  "minDemandScore": 0.35,
  "limit": 50
}'
```

## Call it from Python

```python
from apify_client import ApifyClient

client = ApifyClient("YOUR_APIFY_TOKEN")
run = client.actor("japan-anime-figure-demand-features").call(
    run_input={"hasPriceOnly": True, "minDemandScore": 0.35, "limit": 50}
)
for item in client.dataset(run["defaultDatasetId"]).iterate_items():
    print(item["figureId"], item["demandScore"], item["vector"][:5])
```

## Call it over HTTP

```bash
curl -s "https://api.apify.com/v2/acts/atushi~japan-anime-figure-demand-features/run-sync-get-dataset-items?token=$APIFY_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"hasPriceOnly": true, "limit": 10}' | jq '.[0] | {figureId, demandScore, featureDim}'
```

---

## Output shape

Every dataset item:

| Field | Type | Meaning |
|---|---|---|
| `schemaVersion` | string | Feature-vector schema version (semver) |
| `featureDim` | int | Length of `vector`; always 48 today |
| `figureId` | string | Stable upstream SKU id |
| `name`, `series`, `manufacturer`, `category`, `janCode` | string | Identity |
| `demandScore` | number | Composite demand proxy in `[0,1]` |
| `history` | object | `points`, `firstSeen`, `lastSeen`, `velocityAvailable` |
| `coverage` | object | `hasOfferDetail`, `offerDetailRows`, `hasAggregatePrice`, `hasMsrp`, `hasJan` |
| `features` | object | 48 named features (canonical order) |
| `featureNames` | array | Ordered names; `featureNames[i]` ↔ `vector[i]` |
| `vector` | array | 48 floats in `featureNames` order |

The full schema manifest ships in the run's key-value store as
`FEATURE_MANIFEST` (dimension, ordered names, per-dimension documentation and
normalization constants). Fetch it once and build your column mapping from it
instead of hard-coding indices.

## Feature groups

| Group | Count | Examples |
|---|---|---|
| Price | 8 | `price_min_norm`, `msrp_norm`, `discount_depth`, `premium_ratio` |
| Supply | 8 | `stock_ratio`, `offer_count_norm`, `shop_diversity_ratio` |
| Cross-shop dispersion | 4 | `shop_price_cv`, `cheapest_shop_advantage`, `instock_price_premium` |
| Temporal | 8 | `age_days_norm`, `release_year_norm`, `velocity_7d`, `history_available` |
| Metadata completeness | 8 | `has_msrp`, `has_jan`, `confidence` |
| Categorical / identity | 8 | `is_scale_figure`, `manufacturer_pop_norm`, hash-bucket embeddings |
| Relative price rank | 3 | `price_rank_in_series`, `price_rank_in_category`, `price_rank_in_manufacturer` |
| Composite | 1 | `demand_score` |

Normalization: every component lies in `[0,1]`, except `instock_price_premium`
and `velocity_*` which are clipped to `[-1,1]`. Absolute prices are divided by
50,000 JPY and offer counts by 30 — both constants are exposed in the manifest.

### `demand_score`

```
demand_score = 0.35 * stock_ratio
             + 0.25 * log_offer_count_norm
             + 0.20 * discount_depth
             + 0.10 * (1 - age_days_norm)
             + 0.10 * (1 - price_spread_ratio)
```

A supply-side demand-pressure proxy. It is **not** a forecast and has **not**
been back-tested against realised sales.

---

## Limitations

* **Single collection point.** The shipped upstream snapshot was captured on
  one date, so `history.points` is `1` for the 132 rows that carry offer
  detail and `0` for the rest. `velocity_7d` / `velocity_30d` are therefore
  emitted as `0.0`. Gate on `history_available == 1.0` before using velocity
  features; where it is `0.0` the values carry no information.
* **Aggregate-only rows.** 181 upstream rows advertise a non-zero offer count
  (and often a price) while shipping an empty `offers[]` array. Price features
  still resolve from the aggregate figures, but every per-shop feature
  (`shop_price_cv`, `shop_price_range_ratio`, `cheapest_shop_advantage`,
  `distinct_shop_norm`, `shop_diversity_ratio`, `instock_price_premium`) is
  `0.0` for them — read `coverage.hasOfferDetail` first, or pass
  `requireOfferDetail: true`.
* **Sparse price coverage.** 292 of 654 upstream rows carry a price; the rest
  have metadata only. Use `hasPriceOnly: true` to exclude them.
* **Hash-bucket embeddings.** `manufacturer_bucket_norm` and friends are
  deterministic SHA-256 buckets, not trained embeddings. They give models a
  stable categorical signal, not semantics.
* **Japan-market scope.** Figures, hobby goods and their secondary market only.

## Pricing

Pay-Per-Event, **$0.002 per dataset item returned** — the account-standard
price point shared by 46 of 73 portfolio Actors. A one-time Actor-start event
applies per run (`$0.00005` per GB of memory). No subscription, no minimum.

## Input reference

| Field | Type | Default | Notes |
|---|---|---|---|
| `figureIds` | string[] | – | Restrict to specific upstream SKUs |
| `series` / `character` / `manufacturer` | string | – | Case-insensitive partial match |
| `categories` | string[] | – | `Scale Figure`, `Anime Figure` |
| `minDemandScore` / `maxDemandScore` | number | – | Filter on `demandScore` |
| `hasPriceOnly` | bool | `false` | Drop rows with no observed price |
| `requireOfferDetail` | bool | `false` | Drop rows with an empty `offers[]` |
| `includeFeatures` | bool | `true` | Attach named feature dict |
| `includeVector` | bool | `true` | Attach ordered vector |
| `limit` / `offset` | int | `100` / `0` | Ordered by descending `demandScore`, then `figureId` |

## Provenance

Upstream dataset: `japan-anime-figure-price-data` (MyFigureList primary, 23
distinct shops observed, JAN/GTIN keyed where available). Each record carries
`sourcesMerged` and `confidence` from the upstream collector via
`provenance` in the manifest pipeline.

## License

MIT.
