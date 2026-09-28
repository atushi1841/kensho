#!/usr/bin/env python3
"""
Apify Actor: Japan Anime Figure Demand Feature Vectors
======================================================

Turns the already-collected normalized Japan anime/figure price snapshot into
fixed-dimension, normalized feature vectors for AI agents, ML pipelines and
quant research — no new scraping, no network calls.

Upstream data: `japan-anime-figure-price-data` (654 normalized rows,
multi-shop offers). This actor re-projects that snapshot as a
machine-consumable feature matrix.

Pricing: Apify Pay-Per-Event, $0.002 per dataset item returned
(account-standard — matches 46/73 portfolio actors).

Outputs
-------
1. Per-item records pushed to the default dataset (one PPE event each):
   identity + `features` (named dict) + `vector` (fixed 48-dim list) +
   `history` provenance.
2. `FEATURE_MANIFEST` in the key-value store describing the schema:
   version, dimension, ordered feature names and normalization constants.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from apify import Actor

from feature_vectors import (
    FEATURE_DIM,
    SCHEMA_VERSION,
    DatasetContext,
    build_record,
    feature_manifest,
    load_rows,
)

_HERE = Path(__file__).resolve().parent

# Self-contained actor package: prefer the bundled data dir, fall back to the
# repo data dir when running from a checkout.
_DATA_CANDIDATES = (
    _HERE / "data" / "anime_figure_prices_normalized.jsonl",
    _HERE.parent / "data" / "anime_figure_prices_normalized.jsonl",
    _HERE / "data" / "anime_figure_prices_normalized_v2.jsonl",
    _HERE.parent / "data" / "anime_figure_prices_normalized_v2.jsonl",
)


def _resolve_dataset() -> Path:
    for candidate in _DATA_CANDIDATES:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "Normalized figure dataset not found. Looked in: "
        + ", ".join(str(c) for c in _DATA_CANDIDATES)
    )


def _matches(
    row: dict[str, Any],
    figure_ids: list[str] | None,
    series: str | None,
    character: str | None,
    manufacturer: str | None,
    categories: list[str] | None,
    min_demand: float | None,
    max_demand: float | None,
    has_price: bool,
    require_offer_detail: bool,
) -> bool:
    if figure_ids and str(row.get("figure_id")) not in {str(i) for i in figure_ids}:
        return False
    if series and series.lower() not in (row.get("series") or "").lower():
        return False
    if character and character.lower() not in (row.get("character") or "").lower():
        return False
    if manufacturer and manufacturer.lower() not in (row.get("manufacturer") or "").lower():
        return False
    if categories and (row.get("category") or "") not in set(categories):
        return False
    if has_price and row.get("lowest_price_jpy") is None and row.get("highest_price_jpy") is None:
        return False
    if require_offer_detail and not [o for o in (row.get("offers") or []) if isinstance(o, dict)]:
        return False
    # demand filters are applied post-computation (see caller)
    return True


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        figure_ids = actor_input.get("figureIds")
        series = actor_input.get("series")
        character = actor_input.get("character")
        manufacturer = actor_input.get("manufacturer")
        categories = actor_input.get("categories")
        min_demand = actor_input.get("minDemandScore")
        max_demand = actor_input.get("maxDemandScore")
        has_price = bool(actor_input.get("hasPriceOnly", False))
        require_offer_detail = bool(actor_input.get("requireOfferDetail", False))
        include_features = bool(actor_input.get("includeFeatures", True))
        include_vector = bool(actor_input.get("includeVector", True))
        limit = int(actor_input.get("limit", 100))
        offset = int(actor_input.get("offset", 0))

        try:
            data_path = _resolve_dataset()
        except FileNotFoundError as exc:
            await Actor.fail(str(exc))
            return

        Actor.log.info(f"Loading normalized figure data from {data_path}")
        rows = load_rows(data_path)
        Actor.log.info(f"Loaded {len(rows)} rows; building dataset context")

        ctx = DatasetContext(rows)
        now = datetime.now(timezone.utc)

        # Metadata filters first (cheap), then compute features, then score filters.
        prefiltered = [
            r
            for r in rows
            if _matches(
                r,
                figure_ids,
                series,
                character,
                manufacturer,
                categories,
                min_demand,
                max_demand,
                has_price,
                require_offer_detail,
            )
        ]
        Actor.log.info(f"After metadata filters: {len(prefiltered)} rows")

        records = []
        for row in prefiltered:
            record = build_record(row, ctx, now=now)
            if min_demand is not None and record["demandScore"] < float(min_demand):
                continue
            if max_demand is not None and record["demandScore"] > float(max_demand):
                continue
            records.append(record)

        # Stable ordering: descending demand score, then figureId, so pagination
        # is deterministic across runs.
        records.sort(key=lambda r: (-r["demandScore"], r["figureId"]))

        page = records[offset : offset + limit]
        Actor.log.info(
            f"Returning {len(page)} of {len(records)} matching records "
            f"(offset={offset}, limit={limit})"
        )

        # Shrink payload when the consumer only wants the vector / score.
        emitted: list[dict[str, Any]] = []
        for record in page:
            out = {
                "schemaVersion": record["schemaVersion"],
                "featureDim": record["featureDim"],
                "figureId": record["figureId"],
                "name": record["name"],
                "series": record["series"],
                "manufacturer": record["manufacturer"],
                "category": record["category"],
                "janCode": record["janCode"],
                "currency": record["currency"],
                "demandScore": record["demandScore"],
                "coverage": record["coverage"],
                "history": record["history"],
            }
            if include_features:
                out["features"] = record["features"]
                out["featureNames"] = record["featureNames"]
            if include_vector:
                out["vector"] = record["vector"]
            emitted.append(out)

        # PPE: one event per item returned.
        for item in emitted:
            await Actor.push_data(item)

        manifest = feature_manifest()
        await Actor.set_value("FEATURE_MANIFEST", manifest)
        await Actor.set_value(
            "OUTPUT",
            {
                "schemaVersion": SCHEMA_VERSION,
                "featureDim": FEATURE_DIM,
                "items": emitted,
                "total": len(records),
                "returned": len(emitted),
                "limit": limit,
                "offset": offset,
                "generatedAt": now.isoformat(),
            },
        )
        Actor.log.info(
            f"Done. schemaVersion={SCHEMA_VERSION} featureDim={FEATURE_DIM} "
            f"items={len(emitted)} total={len(records)}"
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
