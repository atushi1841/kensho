"""pytest suite for the demand feature-vector actor.

Runs from the actor directory:

    cd apify-figure-feature-vectors && python -m pytest tests/ -q

The module under test is pure stdlib (``feature_vectors.py``), so these tests
need no Apify SDK and no network.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ACTOR_DIR = Path(__file__).resolve().parent.parent
if str(ACTOR_DIR) not in sys.path:
    sys.path.insert(0, str(ACTOR_DIR))

from feature_vectors import (  # noqa: E402
    FEATURE_DIM,
    FEATURE_DOCS,
    FEATURE_NAMES,
    PRICE_SCALE_JPY,
    SCHEMA_VERSION,
    DatasetContext,
    build_features,
    build_record,
    feature_manifest,
    load_rows,
    to_vector,
)

DATA_FILE = ACTOR_DIR / "data" / "anime_figure_prices_normalized.jsonl"
NOW = datetime(2026, 9, 28, tzinfo=timezone.utc)


def _row(**overrides):
    """Minimal synthetic dataset row, overridable per test."""
    row = {
        "figure_id": "t-1",
        "name": "Test Figure",
        "series": "Test Series",
        "character": "Test Character",
        "manufacturer": "Test Mfr",
        "category": "Scale Figure",
        "release_date": "2020-01-01",
        "scale": "1/7",
        "sculptor": "Someone",
        "height_cm": 25,
        "jan_code": "4900000000001",
        "msrp_jpy": 10000,
        "lowest_price_jpy": 8000,
        "highest_price_jpy": 12000,
        "in_stock_count": 2,
        "total_offers_count": 4,
        "confidence": 0.9,
        "fetched_at": "2026-09-27T10:00:00",
        "sources_merged": ["jsonl"],
        "offers": [
            {"shop_name": "A", "price_jpy": 8000, "availability": "InStock", "condition": "NewCondition", "fetched_at": "2026-09-27T10:00:00"},
            {"shop_name": "B", "price_jpy": 9000, "availability": "OutOfStock", "condition": "NewCondition", "fetched_at": "2026-09-27T10:00:00"},
            {"shop_name": "C", "price_jpy": 11000, "availability": "InStock", "condition": "UsedCondition", "fetched_at": "2026-09-27T10:00:00"},
            {"shop_name": "D", "price_jpy": 12000, "availability": "PreOrder", "condition": "NewCondition", "fetched_at": "2026-09-27T10:00:00"},
        ],
    }
    row.update(overrides)
    return row


# --------------------------------------------------------------------------
# Schema contract
# --------------------------------------------------------------------------

def test_feature_dim_is_48_and_unique():
    assert FEATURE_DIM == 48
    assert len(set(FEATURE_NAMES)) == FEATURE_DIM


def test_every_dimension_is_documented():
    undocumented = [n for n in FEATURE_NAMES if n not in FEATURE_DOCS]
    assert undocumented == []


def test_schema_version_is_semver():
    parts = SCHEMA_VERSION.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


def test_manifest_matches_module_contract():
    man = feature_manifest()
    assert man["schemaVersion"] == SCHEMA_VERSION
    assert man["featureDim"] == FEATURE_DIM
    assert man["featureNames"] == list(FEATURE_NAMES)
    assert man["normalization"]["priceScaleJpy"] == PRICE_SCALE_JPY


# --------------------------------------------------------------------------
# Feature semantics
# --------------------------------------------------------------------------

def test_vector_length_and_order_match_names():
    ctx = DatasetContext([_row()])
    feats = build_features(_row(), ctx, now=NOW)
    assert list(feats.keys()) == list(FEATURE_NAMES)
    assert len(to_vector(feats)) == FEATURE_DIM


def test_all_components_normalized_to_unit_range():
    ctx = DatasetContext([_row()])
    feats = build_features(_row(), ctx, now=NOW)
    signed = {"instock_price_premium", "velocity_7d", "velocity_30d"}
    for name, value in feats.items():
        assert isinstance(value, float), name
        lo, hi = (-1.0, 1.0) if name in signed else (0.0, 1.0)
        assert lo - 1e-6 <= value <= hi + 1e-6, (name, value)


def test_known_offer_aggregates():
    ctx = DatasetContext([_row()])
    feats = build_features(_row(), ctx, now=NOW)
    # 4 offers, 2 in stock, 4 distinct shops
    assert feats["offer_count_norm"] == pytest.approx(4 / 30, abs=1e-4)
    assert feats["stock_ratio"] == pytest.approx(0.5)
    assert feats["out_of_stock_ratio"] == pytest.approx(0.25)
    assert feats["preorder_ratio"] == pytest.approx(0.25)
    assert feats["distinct_shop_norm"] == pytest.approx(4 / 23, abs=1e-4)
    assert feats["condition_new_ratio"] == pytest.approx(0.75)
    assert feats["price_min_norm"] == pytest.approx(8000 / PRICE_SCALE_JPY, abs=1e-4)
    # (10000 - 8000) / 10000
    assert feats["discount_depth"] == pytest.approx(0.2, abs=1e-4)
    assert feats["premium_ratio"] == pytest.approx(0.0)
    assert feats["has_msrp"] == 1.0


def test_premium_when_price_exceeds_msrp():
    ctx = DatasetContext([_row()])
    feats = build_features(_row(msrp_jpy=5000, lowest_price_jpy=10000), ctx, now=NOW)
    assert feats["premium_ratio"] == pytest.approx(1.0)  # clipped
    assert feats["discount_depth"] == pytest.approx(0.0)


def test_missing_msrp_yields_zero_discount_not_crash():
    ctx = DatasetContext([_row()])
    feats = build_features(_row(msrp_jpy=None), ctx, now=NOW)
    assert feats["has_msrp"] == 0.0
    assert feats["msrp_norm"] == 0.0
    assert feats["discount_depth"] == 0.0


def test_empty_offers_are_safe():
    ctx = DatasetContext([_row()])
    feats = build_features(
        _row(offers=[], total_offers_count=0, in_stock_count=0,
             lowest_price_jpy=None, highest_price_jpy=None),
        ctx, now=NOW,
    )
    assert feats["stock_ratio"] == 0.0
    assert feats["price_mid_norm"] == 0.0
    assert feats["shop_price_cv"] == 0.0


def test_single_shop_dispersion_is_zero():
    one = _row(offers=[{"shop_name": "A", "price_jpy": 9000, "availability": "InStock",
                        "condition": "NewCondition", "fetched_at": "2026-09-27T10:00:00"}])
    feats = build_features(one, DatasetContext([one]), now=NOW)
    assert feats["shop_price_cv"] == 0.0
    assert feats["shop_price_range_ratio"] == 0.0
    assert feats["cheapest_shop_advantage"] == 0.0


def test_cheapest_shop_per_shop_dedup():
    """Repeated (shop, price) offer pairs must not inflate the shop count."""
    offers = [
        {"shop_name": "A", "price_jpy": 8000, "availability": "InStock", "condition": "NewCondition", "fetched_at": "2026-09-27T10:00:00"},
        {"shop_name": "A", "price_jpy": 9500, "availability": "InStock", "condition": "NewCondition", "fetched_at": "2026-09-27T10:00:00"},
    ]
    row = _row(offers=offers)
    feats = build_features(row, DatasetContext([row]), now=NOW)
    assert feats["shop_diversity_ratio"] == pytest.approx(0.5)  # 1 distinct shop / 2 offers
    assert feats["shop_price_cv"] == 0.0  # single shop -> no dispersion


def test_upcoming_release_flagged():
    future = (NOW + timedelta(days=200)).date().isoformat()
    feats = build_features(_row(release_date=future), DatasetContext([_row()]), now=NOW)
    assert feats["is_upcoming"] == 1.0
    assert feats["age_days_norm"] == 0.0


def test_history_features_single_snapshot():
    ctx = DatasetContext([_row()])
    feats = build_features(_row(), ctx, now=NOW)
    assert feats["history_available"] == 0.0
    assert feats["velocity_7d"] == 0.0
    assert feats["velocity_30d"] == 0.0
    assert feats["history_points_norm"] == pytest.approx(1 / 30, abs=1e-4)


def test_history_features_two_snapshots_flag_on():
    offers = [
        {"shop_name": "A", "price_jpy": 8000, "availability": "InStock", "condition": "NewCondition", "fetched_at": "2026-09-20T10:00:00"},
        {"shop_name": "A", "price_jpy": 7500, "availability": "InStock", "condition": "NewCondition", "fetched_at": "2026-09-27T10:00:00"},
    ]
    row = _row(offers=offers)
    feats = build_features(row, DatasetContext([row]), now=NOW)
    assert feats["history_available"] == 1.0
    assert feats["history_points_norm"] == pytest.approx(2 / 30, abs=1e-4)


def test_demand_score_matches_formula():
    ctx = DatasetContext([_row()])
    f = build_features(_row(), ctx, now=NOW)
    expected = (
        0.35 * f["stock_ratio"]
        + 0.25 * f["log_offer_count_norm"]
        + 0.20 * f["discount_depth"]
        + 0.10 * (1 - f["age_days_norm"])
        + 0.10 * (1 - f["price_spread_ratio"])
    )
    assert f["demand_score"] == pytest.approx(min(max(expected, 0.0), 1.0), abs=1e-5)


def test_unknown_dimension_is_not_silently_invented():
    ctx = DatasetContext([_row()])
    feats = build_features(_row(), ctx, now=NOW)
    assert set(feats) == set(FEATURE_NAMES)


def test_bucket_is_deterministic_and_bounded():
    ctx = DatasetContext([_row(), _row(figure_id="t-2", manufacturer="Other Mfr")])
    a = build_features(_row(), ctx, now=NOW)
    b = build_features(_row(), ctx, now=NOW)
    assert a["manufacturer_bucket_norm"] == b["manufacturer_bucket_norm"]
    assert 0.0 <= a["manufacturer_bucket_norm"] < 1.0
    other = build_features(_row(figure_id="t-2", manufacturer="Other Mfr"), ctx, now=NOW)
    assert other["manufacturer_bucket_norm"] != a["manufacturer_bucket_norm"]


def test_popularity_is_dataset_share():
    rows = [_row(), _row(figure_id="t-2"), _row(figure_id="t-3", manufacturer="Rare")]
    ctx = DatasetContext(rows)
    common = build_features(rows[0], ctx, now=NOW)
    rare = build_features(rows[2], ctx, now=NOW)
    assert common["manufacturer_pop_norm"] == pytest.approx(2 / 3, abs=1e-4)
    assert rare["manufacturer_pop_norm"] == pytest.approx(1 / 3, abs=1e-4)


def test_price_rank_is_percentile_within_group():
    rows = [
        _row(figure_id="a", lowest_price_jpy=1000, highest_price_jpy=1000),
        _row(figure_id="b", lowest_price_jpy=5000, highest_price_jpy=5000),
        _row(figure_id="c", lowest_price_jpy=9000, highest_price_jpy=9000),
    ]
    ctx = DatasetContext(rows)
    low = build_features(rows[0], ctx, now=NOW)
    mid = build_features(rows[1], ctx, now=NOW)
    high = build_features(rows[2], ctx, now=NOW)
    assert low["price_rank_in_series"] < mid["price_rank_in_series"] < high["price_rank_in_series"]
    assert high["price_rank_in_series"] == pytest.approx(5 / 6, abs=1e-4)


# --------------------------------------------------------------------------
# Record assembly & determinism
# --------------------------------------------------------------------------

def test_record_shape_and_provenance():
    row = _row()
    rec = build_record(row, DatasetContext([row]), now=NOW)
    assert rec["schemaVersion"] == SCHEMA_VERSION
    assert rec["featureDim"] == FEATURE_DIM
    assert rec["figureId"] == "t-1"
    assert rec["currency"] == "JPY"
    assert rec["supply"] == {"totalOffers": 4, "inStock": 2, "distinctShops": 4}
    assert rec["coverage"] == {
        "hasOfferDetail": True,
        "offerDetailRows": 4,
        "hasAggregatePrice": True,
        "hasMsrp": True,
        "hasJan": True,
    }
    assert rec["history"] == {
        "points": 1, "firstSeen": "2026-09-27", "lastSeen": "2026-09-27",
        "velocityAvailable": False,
    }
    assert rec["provenance"]["upstreamDataset"] == "japan-anime-figure-price-data"
    assert len(rec["vector"]) == FEATURE_DIM
    assert rec["vector"] == to_vector(rec["features"])


def test_records_are_deterministic():
    rows = [_row(), _row(figure_id="t-2")]
    a = build_record(rows[0], DatasetContext(rows), now=NOW)
    b = build_record(rows[0], DatasetContext(rows), now=NOW)
    assert a == b


# --------------------------------------------------------------------------
# Against the real shipped dataset
# --------------------------------------------------------------------------

@pytest.mark.skipif(not DATA_FILE.exists(), reason="shipped dataset not present")
def test_real_dataset_end_to_end():
    rows = load_rows(DATA_FILE)
    assert len(rows) == 654
    ctx = DatasetContext(rows)
    records = [build_record(r, ctx, now=NOW) for r in rows]
    assert all(len(r["vector"]) == FEATURE_DIM for r in records)
    assert all(list(r["features"]) == list(FEATURE_NAMES) for r in records)
    signed = {"instock_price_premium", "velocity_7d", "velocity_30d"}
    for rec in records:
        for name, value in rec["features"].items():
            lo, hi = (-1.0, 1.0) if name in signed else (0.0, 1.0)
            assert lo - 1e-6 <= value <= hi + 1e-6, (rec["figureId"], name, value)
            assert not math.isnan(value)
    scores = [r["demandScore"] for r in records]
    assert 0.0 <= min(scores) and max(scores) <= 1.0
    # every real row carries at most a single collection point today;
    # rows with no observed offer detail report 0 points.
    assert {r["history"]["points"] for r in records} <= {0, 1}
    with_detail = [r for r in records if r["coverage"]["hasOfferDetail"]]
    assert len(with_detail) == 132
    assert {r["history"]["points"] for r in with_detail} == {1}
    assert all(r["history"]["velocityAvailable"] is False for r in records)
    # Documented upstream inconsistency: rows that advertise an aggregate offer
    # count (and often a price) while shipping an empty offers[] array.
    no_detail_but_count = [
        r
        for r in records
        if not r["coverage"]["hasOfferDetail"] and r["supply"]["totalOffers"] > 0
    ]
    assert len(no_detail_but_count) == 181
    # Shop-dispersion features are only meaningful with offer detail.
    for rec in no_detail_but_count:
        assert rec["features"]["shop_price_cv"] == 0.0
        assert rec["features"]["distinct_shop_norm"] == 0.0


@pytest.mark.skipif(not DATA_FILE.exists(), reason="shipped dataset not present")
def test_real_dataset_json_serializable():
    rows = load_rows(DATA_FILE)[:20]
    ctx = DatasetContext(rows)
    payload = json.dumps([build_record(r, ctx, now=NOW) for r in rows])
    assert len(payload) > 0
