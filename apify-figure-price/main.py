#!/usr/bin/env python3
"""
Apify Actor: Japan Anime Figure Price Data
Pay-per-event pricing at $0.002 per item returned.
Sources: MyFigureList (primary), with extensible architecture for Yahoo Auctions, Mandarake, Suruga-ya, Mercari.
"""

import os
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from apify import Actor
from apify_client import ApifyClient


# Load dataset from the actor package's own data/ dir (self-contained; works deployed too).
# Falls back to the repo data/ dir when running from a checkout.
# Prefers JSONL (richer per-row schema); falls back to CSV (smaller, always shipped).
_HERE = Path(__file__).resolve().parent
DATA_FILE = _HERE / "data" / "anime_figure_prices_normalized.jsonl"
if not DATA_FILE.exists():
    DATA_FILE = _HERE.parent / "data" / "anime_figure_prices_normalized.jsonl"
if not DATA_FILE.exists():
    DATA_FILE = _HERE / "data" / "anime_figure_prices_normalized.csv"
if not DATA_FILE.exists():
    DATA_FILE = _HERE.parent / "data" / "anime_figure_prices_normalized.csv"


def _parse_offers(raw: str) -> list[dict[str, Any]]:
    """Parse the offers JSON column (stored as a JSON string in CSV)."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    # Normalize: CSV export double-quotes JSON string literals -> real JSON after csv parse
    if isinstance(parsed, list):
        return parsed
    return []


def load_dataset() -> list[dict[str, Any]]:
    """Load the normalized figure price dataset (JSONL or CSV)."""
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"Dataset not found at {DATA_FILE}")

    items: list[dict[str, Any]] = []
    if DATA_FILE.suffix == ".jsonl":
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    items.append(json.loads(line))
    else:
        import csv

        with open(DATA_FILE, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # CSV column carries offers as a JSON string
                row["offers"] = _parse_offers(row.get("offers", ""))
                # Coerce numeric fields that come back as strings from CSV
                for key in (
                    "msrp_jpy", "lowest_price_jpy", "highest_price_jpy",
                    "in_stock_count", "total_offers_count", "confidence",
                    "height_cm",
                ):
                    val = row.get(key)
                    if val in (None, ""):
                        row[key] = None if key != "confidence" else 0.95
                        continue
                    try:
                        row[key] = float(val) if key == "confidence" else int(val)
                    except (TypeError, ValueError):
                        row[key] = None if key != "confidence" else 0.95
                items.append(row)
    return items


def filter_items(
    items: list[dict[str, Any]],
    figure_ids: list[str] | None = None,
    series: str | None = None,
    character: str | None = None,
    manufacturer: str | None = None,
    scale: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    condition: str | None = None,
    in_stock_only: bool = False,
) -> list[dict[str, Any]]:
    """Apply filters to the dataset."""
    filtered = []
    
    for item in items:
        # Figure ID filter
        if figure_ids and item.get("figure_id") not in figure_ids:
            continue
        
        # Series filter (partial match)
        if series and series.lower() not in (item.get("series") or "").lower():
            continue
        
        # Character filter (partial match)
        if character and character.lower() not in (item.get("character") or "").lower():
            continue
        
        # Manufacturer filter
        if manufacturer and manufacturer.lower() not in (item.get("manufacturer") or "").lower():
            continue
        
        # Scale filter
        if scale and scale != (item.get("scale") or ""):
            continue
        
        # Price range filters
        lowest = item.get("lowest_price_jpy")
        highest = item.get("highest_price_jpy")
        if min_price is not None and (highest is None or highest < min_price):
            continue
        if max_price is not None and (lowest is None or lowest > max_price):
            continue
        
        # Condition filter
        if condition:
            offers = item.get("offers", [])
            has_condition = any(o.get("condition") == condition for o in offers)
            if not has_condition:
                continue
        
        # In-stock filter
        if in_stock_only:
            in_stock = item.get("in_stock_count", 0)
            if in_stock <= 0:
                continue
        
        filtered.append(item)
    
    return filtered


def transform_item(item: dict[str, Any], include_history: bool = False) -> dict[str, Any]:
    """Transform internal item format to output schema."""
    return {
        "figureId": item.get("figure_id", ""),
        "sourceUrl": item.get("source_url", ""),
        "name": item.get("name", ""),
        "series": item.get("series"),
        "character": item.get("character"),
        "manufacturer": item.get("manufacturer"),
        "category": item.get("category", ""),
        "releaseDate": item.get("release_date"),
        "scale": item.get("scale"),
        "sculptor": item.get("sculptor"),
        "heightCm": item.get("height_cm"),
        "janCode": item.get("jan_code"),
        "imageUrl": item.get("image_url"),
        "offers": item.get("offers", []),
        "msrpJpy": item.get("msrp_jpy"),
        "lowestPriceJpy": item.get("lowest_price_jpy"),
        "highestPriceJpy": item.get("highest_price_jpy"),
        "inStockCount": item.get("in_stock_count", 0),
        "totalOffersCount": item.get("total_offers_count", 0),
        "confidence": item.get("confidence", 0.95),
        "sourcesMerged": item.get("sources_merged", []),
    }


async def main() -> None:
    async with Actor:
        # Get input
        actor_input = await Actor.get_input() or {}
        
        figure_ids = actor_input.get("figureIds")
        series = actor_input.get("series")
        character = actor_input.get("character")
        manufacturer = actor_input.get("manufacturer")
        scale = actor_input.get("scale")
        min_price = actor_input.get("minPrice")
        max_price = actor_input.get("maxPrice")
        condition = actor_input.get("condition")
        in_stock_only = actor_input.get("inStockOnly", False)
        include_history = actor_input.get("includeHistory", False)
        limit = actor_input.get("limit", 100)
        offset = actor_input.get("offset", 0)
        
        # Load dataset
        Actor.log.info(f"Loading dataset from {DATA_FILE}")
        try:
            all_items = load_dataset()
        except FileNotFoundError as e:
            await Actor.fail(str(e))
            return
        
        Actor.log.info(f"Loaded {len(all_items)} figures from dataset")
        
        # Apply filters
        filtered = filter_items(
            all_items,
            figure_ids=figure_ids,
            series=series,
            character=character,
            manufacturer=manufacturer,
            scale=scale,
            min_price=min_price,
            max_price=max_price,
            condition=condition,
            in_stock_only=in_stock_only,
        )
        
        Actor.log.info(f"After filters: {len(filtered)} items")
        
        # Apply pagination
        paginated = filtered[offset : offset + limit]
        
        # Transform to output format
        output_items = [transform_item(item, include_history) for item in paginated]
        
        # Push results to dataset (PPE charges per item)
        for item in output_items:
            await Actor.push_data(item)
        
        # Return summary
        result = {
            "items": output_items,
            "total": len(filtered),
            "limit": limit,
            "offset": offset,
        }
        
        await Actor.set_value("OUTPUT", result)
        Actor.log.info(f"Actor completed: returned {len(output_items)} of {len(filtered)} matching items")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())