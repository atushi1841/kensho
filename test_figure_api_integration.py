#!/usr/bin/env python3
"""Integration test for anime figure pricing API module"""
import asyncio
import json
from kensho.scraping.sources import (
    FigurePriceAggregator,
    PriceSource,
    MyFigureListClient,
    HpoiClient,
    FigureMemoClient,
    get_figure_price,
    search_figures,
    compare_figure_prices,
)


async def test_myfigurelist_fetch():
    """Test MyFigureList client with a known figure URL"""
    print("\n=== Testing MyFigureList fetch ===")
    async with MyFigureListClient() as client:
        # Test with a known figure from sitemap
        try:
            # Try fetching from search first to get valid URLs
            results = await client.search_figures("nendoroid", limit=3)
            print(f"Search results: {len(results)}")
            for r in results[:3]:
                print(f"  {r.name} - ¥{r.lowest_price_jpy} ({r.in_stock_count}/{r.total_offers_count} in stock)")
                print(f"    URL: {r.source_url}")
                print(f"    ID: {r.figure_id}")
                print(f"    Series: {r.series}")
                print(f"    Category: {r.category}")
        except Exception as e:
            print(f"Error: {e}")


async def test_aggregator_search():
    """Test aggregator search across all sources"""
    print("\n=== Testing Aggregator Search ===")
    async with FigurePriceAggregator() as agg:
        try:
            results = await agg.search_all_sources("nendoroid", limit=3)
            for source, items in results.items():
                print(f"\n{source.value}: {len(items)} results")
                for item in items[:3]:
                    print(f"  {item.name} - ¥{item.lowest_price_jpy} ({item.in_stock_count}/{item.total_offers_count} in stock)")
        except Exception as e:
            print(f"Error: {e}")


async def test_aggregator_compare():
    """Test price comparison for a specific figure"""
    print("\n=== Testing Price Comparison ===")
    async with FigurePriceAggregator() as agg:
        # First search to get a valid identifier
        try:
            results = await agg.search_all_sources("frieren nendoroid", limit=1)
            for source, items in results.items():
                if items:
                    item = items[0]
                    print(f"Testing comparison for: {item.name} (from {source.value})")
                    print(f"  Source URL: {item.source_url}")
                    
                    # Now compare prices for this figure across all sources
                    compare_result = await agg.compare_prices(item.source_url)
                    print(f"\nComparison result:")
                    print(json.dumps(compare_result, ensure_ascii=False, indent=2))
                    break
        except Exception as e:
            print(f"Error: {e}")


async def test_get_figure_price():
    """Test convenience function"""
    print("\n=== Testing get_figure_price convenience function ===")
    async with FigurePriceAggregator() as agg:
        try:
            results = await agg.search_all_sources("scale figure", limit=1)
            for source, items in results.items():
                if items:
                    item = items[0]
                    print(f"Fetching best price for: {item.name}")
                    best = await get_figure_price(item.source_url)
                    if best:
                        print(f"Best price: ¥{best.lowest_price_jpy} from {best.source.value}")
                        print(f"Total offers: {best.total_offers_count}, In stock: {best.in_stock_count}")
                    break
        except Exception as e:
            print(f"Error: {e}")


async def main():
    print("Running integration tests for anime figure pricing API...")
    
    # Test individual clients
    await test_myfigurelist_fetch()
    
    # Test aggregator
    await test_aggregator_search()
    
    # Test comparison
    await test_aggregator_compare()
    
    # Test convenience function
    await test_get_figure_price()
    
    print("\n=== All integration tests completed ===")


if __name__ == "__main__":
    asyncio.run(main())