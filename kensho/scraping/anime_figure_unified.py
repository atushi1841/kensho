#!/usr/bin/env python3
"""Unified Anime Figure Price Data Collector

Collects anime figure price history, release dates, and version-specific information
from Hpoi API, figurememo, and MyFigureList to create a comprehensive price dataset
for collectors/traders to sell on Gumroad.

Features:
- Multi-source price aggregation (MyFigureList + Hpoi API + FigureMemo)
- Unified data format with confidence scoring
- Deduplication across sources
- Gumroad-ready CSV/JSON export
- Low TOS risk (public APIs only)
"""

from __future__ import annotations

import asyncio
import csv
import json
import logging
import os
import random
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from .sources.anime_figure_api import (
    PriceSource,
    FigurePrice,
    FigurePriceAggregator,
    MyFigureListClient,
    HpoiClient,
    FigureMemoClient,
)

logger = logging.getLogger(__name__)


class UnifiedFigureCollector:
    """Unified collector that aggregates data from all three sources"""

    def __init__(
        self,
        output_dir: str = "data",
        max_figures: int = 10000,
        rate_limit_rpm: int = 20,
        enable_myfigurelist: bool = True,
        enable_hpoi: bool = True,
        enable_figurememo: bool = True,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_figures = max_figures
        self.rate_limit_rpm = rate_limit_rpm
        self.enable_myfigurelist = enable_myfigurelist
        self.enable_hpoi = enable_hpoi
        self.enable_figurememo = enable_figurememo

    async def collect_all_sources(
        self,
        figure_ids: list[str] | None = None,
        search_query: str | None = None,
        batch_size: int = 50,
    ) -> list[dict[str, Any]]:
        """Collect figure data from all enabled sources
        
        Args:
            figure_ids: Specific figure IDs to collect (if None, uses sitemap discovery)
            search_query: Search query for figure discovery
            batch_size: Number of figures to process in each batch
            
        Returns:
            List of unified figure records with multi-source data
        """
        async with FigurePriceAggregator(
            enable_myfigurelist=self.enable_myfigurelist,
            enable_hpoi=self.enable_hpoi,
            enable_figurememo=self.enable_figurememo,
            cache_ttl=3600,
        ) as aggregator:
            
            if figure_ids:
                # Collect specific figures
                results = []
                for fig_id in figure_ids[:self.max_figures]:
                    result = await aggregator.fetch_best_price(fig_id)
                    if result:
                        results.append(self._to_unified_record(result))
                        if len(results) >= self.max_figures:
                            break
                    await asyncio.sleep(0.1)  # Rate limiting
                return results
            
            elif search_query:
                # Search across all sources
                search_results = await aggregator.search_all_sources(
                    search_query, limit=batch_size
                )
                results = []
                for source, figures in search_results.items():
                    for fig in figures:
                        unified = self._to_unified_record(fig)
                        if unified not in results:
                            results.append(unified)
                        if len(results) >= self.max_figures:
                            break
                return results
            
            else:
                # Full collection from MyFigureList sitemap (primary source)
                return await self._collect_from_sitemap(aggregator, batch_size)

    async def _collect_from_sitemap(
        self, aggregator: FigurePriceAggregator, batch_size: int
    ) -> list[dict[str, Any]]:
        """Collect figures from MyFigureList sitemap and enrich with other sources"""
        mfl_client = aggregator._get_client(PriceSource.MYFIGURELIST)
        if not mfl_client or not isinstance(mfl_client, MyFigureListClient):
            logger.error("MyFigureList client not available")
            return []
        
        # Get figure URLs from sitemap
        urls = await mfl_client.fetch_sitemap_figure_urls()
        logger.info(f"Found {len(urls)} figure URLs from sitemap")
        
        results = []
        seen_ids = set()
        
        # Process in batches
        for i in range(0, min(len(urls), self.max_figures), batch_size):
            batch_urls = urls[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}: {len(batch_urls)} figures")
            
            batch_results = []
            for url in batch_urls:
                # Extract figure ID from URL
                fig_id = self._extract_figure_id(url)
                if fig_id in seen_ids:
                    continue
                
                # Get best price from all sources
                result = await aggregator.fetch_best_price(fig_id)
                if result:
                    unified = self._to_unified_record(result)
                    batch_results.append(unified)
                    seen_ids.add(fig_id)
                
                await asyncio.sleep(0.1)  # Rate limiting
            
            results.extend(batch_results)
            logger.info(f"Batch complete: {len(results)} total figures collected")
            
            if len(results) >= self.max_figures:
                break
        
        return results

    def _extract_figure_id(self, url: str) -> str:
        """Extract figure ID from URL"""
        import re
        # Handle various URL formats
        patterns = [
            r"/figure/(\d+)",
            r"/item/(\d+)",
            r"figure-(\d+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return url

    def _to_unified_record(self, figure_price: FigurePrice) -> dict[str, Any]:
        """Convert FigurePrice to unified record format for Gumroad dataset"""
        record = asdict(figure_price)
        
        # Add metadata for Gumroad dataset
        unified = {
            "figure_id": figure_price.figure_id,
            "name": figure_price.name,
            "name_jp": None,  # Can be populated if available
            "series": figure_price.series,
            "character": figure_price.character,
            "manufacturer": figure_price.manufacturer,
            "category": figure_price.category,
            "release_date": figure_price.release_date,
            "scale": getattr(figure_price, 'scale', None),
            "sculptor": getattr(figure_price, 'sculptor', None),
            "height_cm": getattr(figure_price, 'height_cm', None),
            "jan_code": figure_price.jan_code,
            "image_url": figure_price.image_url,
            "source": figure_price.source.value if hasattr(figure_price.source, 'value') else str(figure_price.source),
            "source_url": figure_price.source_url,
            
            # Price information
            "msrp_jpy": figure_price.msrp_jpy,
            "lowest_price_jpy": figure_price.lowest_price_jpy,
            "highest_price_jpy": figure_price.highest_price_jpy,
            "average_price_jpy": self._calculate_average_price(figure_price),
            "price_range": self._get_price_range(figure_price.lowest_price_jpy, figure_price.highest_price_jpy),
            
            # Availability
            "in_stock_count": figure_price.in_stock_count,
            "total_offers_count": figure_price.total_offers_count,
            "availability_status": self._get_availability_status(figure_price),
            
            # Shop offers (simplified for dataset)
            "shop_offers": [
                {
                    "shop_name": offer.shop_name,
                    "price_jpy": offer.price_jpy,
                    "availability": offer.availability.value if hasattr(offer.availability, 'value') else str(offer.availability),
                    "url": offer.url,
                    "condition": offer.condition,
                }
                for offer in figure_price.offers
            ],
            
            # Metadata
            "fetched_at": figure_price.fetched_at.isoformat() if hasattr(figure_price.fetched_at, 'isoformat') else str(figure_price.fetched_at),
            "confidence": 1.0,  # Will be updated during merge
            "sources_merged": [figure_price.source.value] if hasattr(figure_price.source, 'value') else [str(figure_price.source)],
            
            # Gumroad-specific fields
            "dataset_category": "anime_figures",
            "price_tier": self._get_price_tier(figure_price.lowest_price_jpy),
            "collector_value": self._calculate_collector_value(figure_price),
            "is_limited": self._is_limited_edition(figure_price),
            "is_preorder": figure_price.in_stock_count == 0 and any(
                offer.availability.value == "PreOrder" if hasattr(offer.availability, 'value') 
                else str(offer.availability) == "PreOrder"
                for offer in figure_price.offers
            ),
        }
        
        return unified

    def _calculate_average_price(self, figure_price: FigurePrice) -> float | None:
        """Calculate average price from offers"""
        if not figure_price.offers:
            return None
        prices = [offer.price_jpy for offer in figure_price.offers]
        return sum(prices) / len(prices) if prices else None

    def _get_price_range(self, lowest: int | None, highest: int | None) -> str | None:
        """Get price range string"""
        if lowest is None or highest is None:
            return None
        if lowest == highest:
            return f"¥{lowest:,}"
        return f"¥{lowest:,} - ¥{highest:,}"

    def _get_availability_status(self, figure_price: FigurePrice) -> str:
        """Get overall availability status"""
        if figure_price.in_stock_count > 0:
            return "InStock"
        elif any(
            offer.availability.value == "PreOrder" if hasattr(offer.availability, 'value') 
            else str(offer.availability) == "PreOrder"
            for offer in figure_price.offers
        ):
            return "PreOrder"
        elif any(
            offer.availability.value == "OutOfStock" if hasattr(offer.availability, 'value') 
            else str(offer.availability) == "OutOfStock"
            for offer in figure_price.offers
        ):
            return "OutOfStock"
        return "Unknown"

    def _get_price_tier(self, price: int | None) -> str:
        """Categorize figure by price tier for Gumroad dataset"""
        if price is None:
            return "unknown"
        if price < 1000:
            return "budget"
        elif price < 3000:
            return "standard"
        elif price < 8000:
            return "premium"
        elif price < 20000:
            return "high_end"
        else:
            return "collector"

    def _calculate_collector_value(self, figure_price: FigurePrice) -> float:
        """Calculate collector value score (0-10)"""
        score = 0.0
        
        # Price factor (higher price = more valuable for collectors)
        if figure_price.lowest_price_jpy:
            price_score = min(figure_price.lowest_price_jpy / 20000.0, 5.0)
            score += price_score
        
        # Availability factor (rarer = more valuable)
        if figure_price.total_offers_count > 0:
            availability_score = 5.0 * (1.0 - min(figure_price.in_stock_count / figure_price.total_offers_count, 1.0))
            score += availability_score
        
        # Brand/series factor (popular series = more valuable)
        popular_series = ["鬼滅の刃", "進撃の巨人", "ワンピース", "エヴァンゲリオン", "原神"]
        if figure_price.series and any(series in figure_price.series for series in popular_series):
            score += 2.0
        
        return min(max(score, 0.0), 10.0)

    def _is_limited_edition(self, figure_price: FigurePrice) -> bool:
        """Check if figure is a limited edition"""
        limited_keywords = [
            "limited", "限定", "exclusive", "特典", "special", 
            "anniversary", "記念", "collaboration", "コラボ"
        ]
        name_lower = (figure_price.name or "").lower()
        return any(kw in name_lower for kw in limited_keywords)

    def save_dataset(
        self, 
        records: list[dict[str, Any]],
        format: str = "both",
        filename_prefix: str = "anime_figure_prices_unified",
    ) -> dict[str, Path]:
        """Save collected data in specified format(s)
        
        Args:
            records: List of unified figure records
            format: "json", "csv", or "both"
            filename_prefix: Prefix for output files
            
        Returns:
            Dictionary mapping format to output file paths
        """
        output_files = {}
        
        if format in ("json", "both"):
            # Save as JSON Lines
            jsonl_path = self.output_dir / f"{filename_prefix}.jsonl"
            with jsonl_path.open("w", encoding="utf-8") as f:
                for record in records:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
            output_files["jsonl"] = jsonl_path
            logger.info(f"Saved {len(records)} records to {jsonl_path}")
            
            # Also save as JSON array
            json_path = self.output_dir / f"{filename_prefix}.json"
            with json_path.open("w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False, indent=2)
            output_files["json"] = json_path

        if format in ("csv", "both"):
            # Save as CSV (flattened for spreadsheet compatibility)
            csv_path = self.output_dir / f"{filename_prefix}.csv"
            
            # Flatten records for CSV
            flattened_records = []
            for record in records:
                flat = {}
                for key, value in record.items():
                    if isinstance(value, dict):
                        flat[key] = json.dumps(value, ensure_ascii=False)
                    elif isinstance(value, list):
                        flat[key] = json.dumps(value, ensure_ascii=False)
                    else:
                        flat[key] = value
                flattened_records.append(flat)
            
            # Define CSV columns
            columns = [
                "figure_id", "name", "series", "character", "manufacturer",
                "category", "release_date", "scale", "sculptor", "height_cm",
                "jan_code", "image_url", "source", "source_url",
                "msrp_jpy", "lowest_price_jpy", "highest_price_jpy", "average_price_jpy",
                "price_range", "in_stock_count", "total_offers_count",
                "availability_status", "price_tier", "collector_value",
                "is_limited", "is_preorder", "shop_offers",
                "fetched_at", "confidence", "sources_merged",
                "dataset_category",
            ]
            
            with csv_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(flattened_records)
            
            output_files["csv"] = csv_path
            logger.info(f"Saved {len(records)} records to {csv_path}")
        
        return output_files

    def create_gumroad_metadata(
        self, 
        records: list[dict[str, Any]],
        dataset_name: str = "Anime Figure Price Intelligence",
        dataset_description: str = "Comprehensive anime figure price tracking dataset with multi-source aggregation",
    ) -> dict[str, Any]:
        """Create Gumroad metadata for the dataset
        
        Returns:
            Dictionary with Gumroad product metadata
        """
        # Calculate statistics
        total_figures = len(records)
        total_price = sum(r.get("lowest_price_jpy", 0) or 0 for r in records)
        avg_price = total_price / total_figures if total_figures > 0 else 0
        
        # Count by category
        category_counts = {}
        for record in records:
            category = record.get("category", "unknown")
            category_counts[category] = category_counts.get(category, 0) + 1
        
        # Count by price tier
        tier_counts = {}
        for record in records:
            tier = record.get("price_tier", "unknown")
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
        
        # Count by manufacturer
        manufacturer_counts = {}
        for record in records:
            manufacturer = record.get("manufacturer", "unknown")
            manufacturer_counts[manufacturer] = manufacturer_counts.get(manufacturer, 0) + 1
        
        return {
            "dataset_name": dataset_name,
            "dataset_description": dataset_description,
            "version": "1.0.0",
            "created_at": datetime.now().isoformat(),
            "total_figures": total_figures,
            "total_price_value": total_price,
            "average_price": round(avg_price, 2),
            "category_distribution": category_counts,
            "price_tier_distribution": tier_counts,
            "manufacturer_distribution": manufacturer_counts,
            "data_sources": [
                "MyFigureList" if self.enable_myfigurelist else None,
                "Hpoi API" if self.enable_hpoi else None,
                "FigureMemo" if self.enable_figurememo else None,
            ],
            "update_frequency": "daily",
            "last_updated": datetime.now().isoformat(),
            "recommended_use_cases": [
                "Price comparison for collectors",
                "Market trend analysis",
                "Investment decision making",
                "Inventory valuation",
                "Competitive pricing research",
            ],
            "target_audience": [
                "Anime figure collectors",
                "Resellers and traders",
                "Retailers",
                "Investors",
                "Market researchers",
            ],
            "data_fields": list(records[0].keys()) if records else [],
            "sample_size": min(len(records), 10),
            "sample_records": records[:10] if records else [],
        }


async def run_unified_collection(
    output_dir: str = "data",
    max_figures: int = 1000,
    enable_myfigurelist: bool = True,
    enable_hpoi: bool = True,
    enable_figurememo: bool = True,
    format: str = "both",
    dataset_name: str = "Anime Figure Price Intelligence",
) -> dict[str, Any]:
    """Main entry point for unified anime figure price collection
    
    Args:
        output_dir: Directory to save output files
        max_figures: Maximum number of figures to collect
        enable_myfigurelist: Enable MyFigureList data collection
        enable_hpoi: Enable Hpoi API data collection
        enable_figurememo: Enable FigureMemo data collection
        format: Output format ("json", "csv", "both")
        dataset_name: Name for the Gumroad dataset
        
    Returns:
        Dictionary with results and metadata
    """
    collector = UnifiedFigureCollector(
        output_dir=output_dir,
        max_figures=max_figures,
        enable_myfigurelist=enable_myfigurelist,
        enable_hpoi=enable_hpoi,
        enable_figurememo=enable_figurememo,
    )
    
    # Collect data from all sources
    logger.info("Starting unified anime figure price collection...")
    records = await collector.collect_all_sources()
    logger.info(f"Collected {len(records)} unified figure records")
    
    # Save dataset
    output_files = collector.save_dataset(records, format=format)
    logger.info(f"Saved dataset to: {output_files}")
    
    # Create Gumroad metadata
    metadata = collector.create_gumroad_metadata(records, dataset_name=dataset_name)
    
    # Save metadata
    metadata_path = Path(output_dir) / "anime_figure_dataset_metadata.json"
    with metadata_path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    return {
        "success": True,
        "records_collected": len(records),
        "output_files": {k: str(v) for k, v in output_files.items()},
        "metadata_file": str(metadata_path),
        "metadata": metadata,
        "sources_enabled": {
            "myfigurelist": enable_myfigurelist,
            "hpoi": enable_hpoi,
            "figurememo": enable_figurememo,
        },
        "timestamp": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    import argparse
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    
    parser = argparse.ArgumentParser(
        description="Unified Anime Figure Price Data Collector"
    )
    parser.add_argument("--output", type=str, default="data", 
                        help="Output directory (default: data)")
    parser.add_argument("--max", type=int, default=1000, 
                        help="Maximum figures to collect (default: 1000)")
    parser.add_argument("--format", type=str, default="both",
                        choices=["json", "csv", "both"], 
                        help="Output format (default: both)")
    parser.add_argument("--no-mfl", action="store_true", 
                        help="Disable MyFigureList collection")
    parser.add_argument("--no-hpoi", action="store_true", 
                        help="Disable Hpoi API collection")
    parser.add_argument("--no-fm", action="store_true", 
                        help="Disable FigureMemo collection")
    parser.add_argument("--dataset-name", type=str, 
                        default="Anime Figure Price Intelligence",
                        help="Dataset name for Gumroad")
    
    args = parser.parse_args()
    
    result = asyncio.run(run_unified_collection(
        output_dir=args.output,
        max_figures=args.max,
        enable_myfigurelist=not args.no_mfl,
        enable_hpoi=not args.no_hpoi,
        enable_figurememo=not args.no_fm,
        format=args.format,
        dataset_name=args.dataset_name,
    ))
    
    print(f"\nCollection complete!")
    print(f"Records collected: {result['records_collected']}")
    print(f"Output files: {result['output_files']}")
    print(f"Metadata file: {result['metadata_file']}")
