#!/usr/bin/env python3
"""Test script for anime figure pricing API module"""
from kensho.scraping.sources import (
    FigurePriceAggregator,
    PriceSource,
    get_figure_price,
    search_figures,
    compare_figure_prices,
)

print("Imports OK")

# Quick syntax check - instantiate aggregator
async def test():
    async with FigurePriceAggregator() as agg:
        print("Aggregator created OK")
        print(f"Clients: {[c.source.value for c in agg.clients]}")

import asyncio
asyncio.run(test())
print("Basic test passed!")