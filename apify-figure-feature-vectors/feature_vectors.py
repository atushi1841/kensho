#!/usr/bin/env python3
"""
Feature-vector engineering for the AI Agent Demand Forecasting product.

Transforms the normalized Japan anime figure price rows (produced by
`japan-anime-figure-price-data`) into fixed-dimension, normalized feature
vectors suitable for ML / AI-agent consumption.

Design contract
---------------
* **Fixed dimension.** ``FEATURE_NAMES`` is the canonical ordered schema; the
  emitted ``vector`` list always has ``len(FEATURE_NAMES)`` entries, in that
  exact order. ``SCHEMA_VERSION`` identifies the layout.
* **Normalized.** Every component is a float in ``[0.0, 1.0]`` except
  ``instock_price_premium`` and ``velocity_*`` which are signed / signed-ish
  and therefore clipped to ``[-1.0, 1.0]``.
* **No new data collection.** This module only reads an already-collected
  snapshot; it never touches the network.
* **Honest about history.** The shipped snapshot contains a single collection
  point (see ``history.points``). Time-series features (``velocity_7d``,
  ``velocity_30d``) are emitted as ``0.0`` and are only meaningful when
  ``history_available == 1.0``; consumers must gate on that flag.

Pure stdlib — importable and unit-testable without the Apify SDK.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

# --------------------------------------------------------------------------
# Schema contract
# --------------------------------------------------------------------------

SCHEMA_VERSION = "1.0.0"

#: Maximum plausible JPY price used to normalize all absolute price figures.
PRICE_SCALE_JPY = 50_000.0

#: Maximum plausible offer count used to normalize supply-side counts.
OFFER_SCALE = 30.0

#: Reference datasets observed in the shipped snapshot — used for normalization.
SHOP_UNIVERSE = 23.0
EPOCH_YEAR = 1987.0
YEAR_SPAN = 41.0  # 1987 -> 2028

#: Canonical, ordered feature layout. Index in this list == index in ``vector``.
FEATURE_NAMES: tuple[str, ...] = (
    # --- price block (8) ---
    "price_min_norm",
    "price_max_norm",
    "price_mid_norm",
    "log_price_mid_norm",
    "price_spread_ratio",
    "msrp_norm",
    "discount_depth",
    "premium_ratio",
    # --- supply block (8) ---
    "offer_count_norm",
    "log_offer_count_norm",
    "in_stock_count_norm",
    "stock_ratio",
    "out_of_stock_ratio",
    "preorder_ratio",
    "distinct_shop_norm",
    "shop_diversity_ratio",
    # --- cross-shop dispersion block (4) ---
    "shop_price_cv",
    "shop_price_range_ratio",
    "cheapest_shop_advantage",
    "instock_price_premium",
    # --- temporal block (8) ---
    "age_days_norm",
    "release_year_norm",
    "is_upcoming",
    "days_since_snapshot_norm",
    "history_points_norm",
    "history_available",
    "velocity_7d",
    "velocity_30d",
    # --- metadata completeness block (8) ---
    "has_msrp",
    "has_jan",
    "has_scale",
    "has_sculptor",
    "has_series",
    "has_character",
    "has_height",
    "confidence",
    # --- categorical / identity block (8) ---
    "is_scale_figure",
    "is_anime_figure",
    "condition_new_ratio",
    "manufacturer_pop_norm",
    "series_pop_norm",
    "manufacturer_bucket_norm",
    "series_bucket_norm",
    "character_bucket_norm",
    # --- relative price rank block (3) ---
    "price_rank_in_series",
    "price_rank_in_category",
    "price_rank_in_manufacturer",
    # --- composite (1) ---
    "demand_score",
)

FEATURE_DIM = len(FEATURE_NAMES)
assert FEATURE_DIM == 48, f"expected 48 dims, got {FEATURE_DIM}"

#: Human-readable documentation for each dimension (shipped in the manifest).
FEATURE_DOCS: dict[str, str] = {
    "price_min_norm": "Cheapest listed price / 50000 JPY, clamped [0,1].",
    "price_max_norm": "Most expensive listed price / 50000 JPY, clamped [0,1].",
    "price_mid_norm": "Midpoint of min/max price / 50000 JPY, clamped [0,1].",
    "log_price_mid_norm": "log1p(midpoint) / log1p(50000) — compressed price magnitude.",
    "price_spread_ratio": "(max-min)/max across the item's offers; 0 when <2 prices.",
    "msrp_norm": "Manufacturer suggested retail price / 50000, 0 when unknown.",
    "discount_depth": "Relative discount of cheapest price vs MSRP, [0,1]; 0 w/o MSRP.",
    "premium_ratio": "Relative premium of cheapest price OVER MSRP, clipped [0,1].",
    "offer_count_norm": "Total offer count / 30.",
    "log_offer_count_norm": "log1p(offer count) / log1p(30).",
    "in_stock_count_norm": "In-stock offer count / 30.",
    "stock_ratio": "In-stock offers / total offers.",
    "out_of_stock_ratio": "Out-of-stock offers / total offers.",
    "preorder_ratio": "Pre-order offers / total offers.",
    "distinct_shop_norm": "Distinct shop count / 23 (observed shop universe).",
    "shop_diversity_ratio": "Distinct shops / total offers — one-offer-per-shop signal.",
    "shop_price_cv": "Stddev/mean of per-shop prices, clamped [0,1].",
    "shop_price_range_ratio": "(max-min)/mean of per-shop prices, clamped [0,1].",
    "cheapest_shop_advantage": "(mean-min)/mean of per-shop prices, [0,1].",
    "instock_price_premium": "(mean in-stock price - mean all prices)/mean all, [-1,1].",
    "age_days_norm": "Days since release date / 14000, clamped [0,1].",
    "release_year_norm": "(release year - 1987) / 41, clamped [0,1].",
    "is_upcoming": "1.0 when the release date is in the future relative to the snapshot.",
    "days_since_snapshot_norm": "Days since the snapshot was captured / 365, clamped [0,1].",
    "history_points_norm": "Distinct collection snapshots observed / 30.",
    "history_available": "1.0 when >=2 distinct snapshots exist (velocity is meaningful).",
    "velocity_7d": "Signed 7-day price velocity; 0.0 unless history_available == 1.",
    "velocity_30d": "Signed 30-day price velocity; 0.0 unless history_available == 1.",
    "has_msrp": "1.0 when MSRP is populated.",
    "has_jan": "1.0 when a JAN/GTIN code is populated.",
    "has_scale": "1.0 when the scale field is populated.",
    "has_sculptor": "1.0 when the sculptor field is populated.",
    "has_series": "1.0 when the series field is populated.",
    "has_character": "1.0 when the character field is populated.",
    "has_height": "1.0 when the height field is populated.",
    "confidence": "Source confidence score reported by the upstream collector.",
    "is_scale_figure": "1.0 when category == 'Scale Figure'.",
    "is_anime_figure": "1.0 when category == 'Anime Figure'.",
    "condition_new_ratio": "Share of offers graded NewCondition.",
    "manufacturer_pop_norm": "Share of dataset rows sharing this manufacturer.",
    "series_pop_norm": "Share of dataset rows sharing this series.",
    "manufacturer_bucket_norm": "Deterministic hash bucket of manufacturer / 255 (category embedding).",
    "series_bucket_norm": "Deterministic hash bucket of series / 255 (category embedding).",
    "character_bucket_norm": "Deterministic hash bucket of character / 255 (category embedding).",
    "price_rank_in_series": "Percentile rank of this item's midpoint price within its series.",
    "price_rank_in_category": "Percentile rank of this item's midpoint price within its category.",
    "price_rank_in_manufacturer": "Percentile rank of this item's midpoint price within its manufacturer.",
    "demand_score": "Composite demand proxy (see FEATURE_DOCS_DEMAND_SCORE).",
}

DEMAND_SCORE_DOC = (
    "demand_score = 0.35*stock_ratio + 0.25*log_offer_count_norm "
    "+ 0.20*discount_depth + 0.10*(1-age_days_norm) + 0.10*(1-price_spread_ratio), "
    "clamped [0,1]. Proxy for secondary-market demand pressure derived from "
    "supply-side observables; not a forecast and not back-tested."
)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _clip(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    if value != value:  # NaN guard
        return lo
    return max(lo, min(hi, value))


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_dt(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _bucket(text: Any, buckets: int = 256) -> float:
    """Deterministic, stable hash bucket in [0,1) for a categorical string."""
    if not text:
        return 0.0
    digest = hashlib.sha256(str(text).encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % buckets / float(buckets)


def _mean(values: Sequence[float]) -> float | None:
    vals = [v for v in values]
    if not vals:
        return None
    return sum(vals) / len(vals)


def _stddev(values: Sequence[float]) -> float:
    vals = list(values)
    if len(vals) < 2:
        return 0.0
    mu = sum(vals) / len(vals)
    var = sum((v - mu) ** 2 for v in vals) / len(vals)
    return math.sqrt(var)


def _percentile(value: float, population: Sequence[float]) -> float:
    """Fraction of the population <= value (ties count as half)."""
    if not population:
        return 0.0
    below = sum(1 for p in population if p < value)
    equal = sum(1 for p in population if p == value)
    return _clip((below + 0.5 * equal) / len(population))


# --------------------------------------------------------------------------
# Context (dataset-level statistics)
# --------------------------------------------------------------------------

class DatasetContext:
    """Dataset-level statistics needed for relative / popularity features."""

    def __init__(self, rows: Sequence[dict[str, Any]]) -> None:
        self.rows = list(rows)
        self.n = max(len(self.rows), 1)
        self.manufacturer_counts: dict[str, int] = {}
        self.series_counts: dict[str, int] = {}
        self._prices_by_series: dict[str, list[float]] = {}
        self._prices_by_category: dict[str, list[float]] = {}
        self._prices_by_manufacturer: dict[str, list[float]] = {}

        for row in self.rows:
            mfr = (row.get("manufacturer") or "").strip()
            series = (row.get("series") or "").strip()
            category = (row.get("category") or "").strip()
            if mfr:
                self.manufacturer_counts[mfr] = self.manufacturer_counts.get(mfr, 0) + 1
            if series:
                self.series_counts[series] = self.series_counts.get(series, 0) + 1
            mid = self._midpoint(row)
            if mid is not None:
                if series:
                    self._prices_by_series.setdefault(series, []).append(mid)
                if category:
                    self._prices_by_category.setdefault(category, []).append(mid)
                if mfr:
                    self._prices_by_manufacturer.setdefault(mfr, []).append(mid)

    @staticmethod
    def _midpoint(row: dict[str, Any]) -> float | None:
        lo = _as_float(row.get("lowest_price_jpy"))
        hi = _as_float(row.get("highest_price_jpy"))
        if lo is None and hi is None:
            return None
        if lo is None:
            return hi
        if hi is None:
            return lo
        return (lo + hi) / 2.0

    def popularity(self, counts: dict[str, int], key: str) -> float:
        if not key:
            return 0.0
        return _clip(counts.get(key, 0) / self.n)

    def price_population(self, kind: str, key: str) -> list[float]:
        if kind == "series":
            return self._prices_by_series.get(key, [])
        if kind == "category":
            return self._prices_by_category.get(key, [])
        if kind == "manufacturer":
            return self._prices_by_manufacturer.get(key, [])
        return []


# --------------------------------------------------------------------------
# Feature builder
# --------------------------------------------------------------------------

def build_features(
    row: dict[str, Any],
    ctx: DatasetContext,
    now: datetime | None = None,
) -> dict[str, float]:
    """Compute the named feature dict for a single dataset row.

    The returned dict has exactly ``FEATURE_NAMES`` keys.
    """
    now = now or datetime.now(timezone.utc)

    offers: list[dict[str, Any]] = [
        o for o in (row.get("offers") or []) if isinstance(o, dict)
    ]
    prices = [
        p for p in (_as_float(o.get("price_jpy")) for o in offers) if p is not None
    ]
    in_stock_prices = [
        p
        for o, p in zip(offers, (_as_float(o.get("price_jpy")) for o in offers))
        if p is not None and (o.get("availability") or "") == "InStock"
    ]

    lo = _as_float(row.get("lowest_price_jpy"))
    hi = _as_float(row.get("highest_price_jpy"))
    if lo is None and prices:
        lo = min(prices)
    if hi is None and prices:
        hi = max(prices)
    mid: float | None = None
    if lo is not None and hi is not None:
        mid = (lo + hi) / 2.0
    elif lo is not None:
        mid = lo
    elif hi is not None:
        mid = hi

    msrp = _as_float(row.get("msrp_jpy"))
    total_offers = _as_float(row.get("total_offers_count")) or float(len(offers))
    in_stock = _as_float(row.get("in_stock_count")) or float(len(in_stock_prices))

    # --- supply sub-ratios ---
    availability = [(o.get("availability") or "") for o in offers]
    n_offers = max(len(offers), 1)
    out_of_stock = sum(1 for a in availability if a == "OutOfStock")
    preorder = sum(1 for a in availability if a == "PreOrder")
    distinct_shops = len({(o.get("shop_name") or "").strip() for o in offers if o.get("shop_name")})
    conditions = [(o.get("condition") or "") for o in offers]
    new_ratio = sum(1 for c in conditions if c == "NewCondition") / n_offers

    # --- cross-shop dispersion (one price per shop: cheapest listing per shop) ---
    per_shop: dict[str, float] = {}
    for o in offers:
        price = _as_float(o.get("price_jpy"))
        if price is None:
            continue
        shop = (o.get("shop_name") or "unknown").strip() or "unknown"
        if shop not in per_shop or price < per_shop[shop]:
            per_shop[shop] = price
    shop_prices = list(per_shop.values())
    shop_mean = _mean(shop_prices)
    shop_cv = _clip(_stddev(shop_prices) / shop_mean) if shop_mean else 0.0
    if shop_mean and len(shop_prices) >= 2:
        range_ratio = _clip((max(shop_prices) - min(shop_prices)) / shop_mean)
        cheapest_adv = _clip((shop_mean - min(shop_prices)) / shop_mean)
    else:
        range_ratio = 0.0
        cheapest_adv = 0.0
    instock_mean = _mean(in_stock_prices)
    all_mean = _mean(prices)
    if instock_mean is not None and all_mean:
        instock_premium = _clip((instock_mean - all_mean) / all_mean, -1.0, 1.0)
    else:
        instock_premium = 0.0

    # --- temporal ---
    release = _parse_dt(row.get("release_date"))
    if release:
        age_days = max((now - release).days, 0)
        year_norm = _clip((release.year - EPOCH_YEAR) / YEAR_SPAN)
        is_upcoming = 1.0 if release > now else 0.0
    else:
        age_days = 0
        year_norm = 0.0
        is_upcoming = 0.0

    snapshot = _parse_dt(row.get("fetched_at"))
    days_since_snapshot = max((now - snapshot).days, 0) if snapshot else 0

    # --- history (single-snapshot snapshot today) ---
    snapshots = {(o.get("fetched_at") or "")[:10] for o in offers if o.get("fetched_at")}
    history_points = len(snapshots)
    history_available = 1.0 if history_points >= 2 else 0.0

    # --- metadata flags ---
    has_msrp = 1.0 if msrp is not None else 0.0
    confidence = _as_float(row.get("confidence"))
    if confidence is None:
        confidence = 0.95

    # --- popularity / identity ---
    manufacturer = (row.get("manufacturer") or "").strip()
    series = (row.get("series") or "").strip()
    character = (row.get("character") or "").strip()
    category = (row.get("category") or "").strip()

    # --- relative price ranks ---
    rank_series = rank_category = rank_mfr = 0.0
    if mid is not None:
        rank_series = _percentile(mid, ctx.price_population("series", series))
        rank_category = _percentile(mid, ctx.price_population("category", category))
        rank_mfr = _percentile(mid, ctx.price_population("manufacturer", manufacturer))

    features: dict[str, float] = {
        "price_min_norm": _clip((lo or 0.0) / PRICE_SCALE_JPY),
        "price_max_norm": _clip((hi or 0.0) / PRICE_SCALE_JPY),
        "price_mid_norm": _clip((mid or 0.0) / PRICE_SCALE_JPY),
        "log_price_mid_norm": _clip(
            math.log1p(mid or 0.0) / math.log1p(PRICE_SCALE_JPY)
        ),
        "price_spread_ratio": (
            _clip(((hi - lo) / hi)) if (lo is not None and hi and hi > lo) else 0.0
        ),
        "msrp_norm": _clip((msrp or 0.0) / PRICE_SCALE_JPY),
        "discount_depth": (
            _clip((msrp - lo) / msrp) if (msrp and lo is not None and msrp > lo) else 0.0
        ),
        "premium_ratio": (
            _clip((lo - msrp) / msrp) if (msrp and lo is not None and lo > msrp) else 0.0
        ),
        "offer_count_norm": _clip(total_offers / OFFER_SCALE),
        "log_offer_count_norm": _clip(
            math.log1p(total_offers) / math.log1p(OFFER_SCALE)
        ),
        "in_stock_count_norm": _clip(in_stock / OFFER_SCALE),
        "stock_ratio": _clip(in_stock / total_offers) if total_offers else 0.0,
        "out_of_stock_ratio": _clip(out_of_stock / n_offers),
        "preorder_ratio": _clip(preorder / n_offers),
        "distinct_shop_norm": _clip(distinct_shops / SHOP_UNIVERSE),
        "shop_diversity_ratio": _clip(distinct_shops / n_offers),
        "shop_price_cv": shop_cv,
        "shop_price_range_ratio": range_ratio,
        "cheapest_shop_advantage": cheapest_adv,
        "instock_price_premium": instock_premium,
        "age_days_norm": _clip(age_days / 14000.0),
        "release_year_norm": year_norm,
        "is_upcoming": is_upcoming,
        "days_since_snapshot_norm": _clip(days_since_snapshot / 365.0),
        "history_points_norm": _clip(history_points / 30.0),
        "history_available": history_available,
        "velocity_7d": 0.0,
        "velocity_30d": 0.0,
        "has_msrp": has_msrp,
        "has_jan": 1.0 if row.get("jan_code") else 0.0,
        "has_scale": 1.0 if row.get("scale") else 0.0,
        "has_sculptor": 1.0 if row.get("sculptor") else 0.0,
        "has_series": 1.0 if series else 0.0,
        "has_character": 1.0 if character else 0.0,
        "has_height": 1.0 if row.get("height_cm") is not None else 0.0,
        "confidence": _clip(confidence),
        "is_scale_figure": 1.0 if category == "Scale Figure" else 0.0,
        "is_anime_figure": 1.0 if category == "Anime Figure" else 0.0,
        "condition_new_ratio": _clip(new_ratio),
        "manufacturer_pop_norm": ctx.popularity(ctx.manufacturer_counts, manufacturer),
        "series_pop_norm": ctx.popularity(ctx.series_counts, series),
        "manufacturer_bucket_norm": _bucket(manufacturer),
        "series_bucket_norm": _bucket(series),
        "character_bucket_norm": _bucket(character),
        "price_rank_in_series": rank_series,
        "price_rank_in_category": rank_category,
        "price_rank_in_manufacturer": rank_mfr,
        "demand_score": 0.0,  # filled below
    }

    features["demand_score"] = _clip(
        0.35 * features["stock_ratio"]
        + 0.25 * features["log_offer_count_norm"]
        + 0.20 * features["discount_depth"]
        + 0.10 * (1.0 - features["age_days_norm"])
        + 0.10 * (1.0 - features["price_spread_ratio"])
    )

    return {name: round(float(features[name]), 6) for name in FEATURE_NAMES}


def to_vector(features: dict[str, float]) -> list[float]:
    """Order a feature dict into the canonical fixed-length vector."""
    return [float(features[name]) for name in FEATURE_NAMES]


def build_record(
    row: dict[str, Any],
    ctx: DatasetContext,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build a full output record (identity + features + vector + provenance)."""
    features = build_features(row, ctx, now=now)
    vector = to_vector(features)

    offers = [o for o in (row.get("offers") or []) if isinstance(o, dict)]
    snapshots = sorted(
        {(o.get("fetched_at") or "")[:10] for o in offers if o.get("fetched_at")}
    )
    has_aggregate_price = (
        _as_float(row.get("lowest_price_jpy")) is not None
        or _as_float(row.get("highest_price_jpy")) is not None
    )
    return {
        "schemaVersion": SCHEMA_VERSION,
        "featureDim": FEATURE_DIM,
        "figureId": str(row.get("figure_id") or ""),
        "janCode": row.get("jan_code"),
        "name": row.get("name") or "",
        "series": row.get("series"),
        "character": row.get("character"),
        "manufacturer": row.get("manufacturer"),
        "category": row.get("category"),
        "releaseDate": row.get("release_date"),
        "currency": "JPY",
        "price": {
            "lowest": _as_float(row.get("lowest_price_jpy")),
            "highest": _as_float(row.get("highest_price_jpy")),
            "msrp": _as_float(row.get("msrp_jpy")),
        },
        "supply": {
            "totalOffers": int(_as_float(row.get("total_offers_count")) or len(offers)),
            "inStock": int(_as_float(row.get("in_stock_count")) or 0),
            "distinctShops": len(
                {(o.get("shop_name") or "").strip() for o in offers if o.get("shop_name")}
            ),
        },
        # Which parts of the upstream row actually carried data. The upstream
        # snapshot has rows that report aggregate offer counts/prices while
        # shipping an empty offers[] array, so per-shop features (dispersion,
        # shop counts) are only trustworthy when ``hasOfferDetail`` is true.
        "coverage": {
            "hasOfferDetail": bool(offers),
            "offerDetailRows": len(offers),
            "hasAggregatePrice": has_aggregate_price,
            "hasMsrp": _as_float(row.get("msrp_jpy")) is not None,
            "hasJan": bool(row.get("jan_code")),
        },
        "history": {
            "points": len(snapshots),
            "firstSeen": snapshots[0] if snapshots else None,
            "lastSeen": snapshots[-1] if snapshots else None,
            "velocityAvailable": len(snapshots) >= 2,
        },
        "demandScore": features["demand_score"],
        "features": features,
        "featureNames": list(FEATURE_NAMES),
        "vector": vector,
        "provenance": {
            "upstreamDataset": "japan-anime-figure-price-data",
            "upstreamSources": row.get("sources_merged", []),
            "confidence": _as_float(row.get("confidence")),
        },
    }


def load_rows(path: str | Path) -> list[dict[str, Any]]:
    """Load normalized figure rows from a JSONL dataset."""
    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def feature_manifest() -> dict[str, Any]:
    """Machine-readable schema manifest — shipped as the actor's KV output."""
    return {
        "schemaVersion": SCHEMA_VERSION,
        "featureDim": FEATURE_DIM,
        "featureNames": list(FEATURE_NAMES),
        "documentation": {**FEATURE_DOCS, "demand_score_formula": DEMAND_SCORE_DOC},
        "normalization": {
            "priceScaleJpy": PRICE_SCALE_JPY,
            "offerScale": OFFER_SCALE,
            "shopUniverse": SHOP_UNIVERSE,
            "epochYear": EPOCH_YEAR,
            "yearSpan": YEAR_SPAN,
        },
        "notes": [
            "All components are normalized to [0,1] except instock_price_premium "
            "and velocity_* which are clipped to [-1,1].",
            "velocity_7d/velocity_30d are 0.0 and are only meaningful when "
            "history_available == 1.0; the shipped snapshot has a single collection date.",
            "demand_score is a supply-side proxy, not a back-tested forecast.",
        ],
    }


def iter_records(
    rows: Iterable[dict[str, Any]],
    ctx: DatasetContext | None = None,
    now: datetime | None = None,
) -> Iterable[dict[str, Any]]:
    """Convenience generator over records."""
    rows = list(rows)
    ctx = ctx or DatasetContext(rows)
    for row in rows:
        yield build_record(row, ctx, now=now)
