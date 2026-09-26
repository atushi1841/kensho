"""nongsan-mcp: Japanese agricultural market data MCP server.

Exposes tools for querying MAFF/e-Stat agricultural price data:
- nongsan_current_price: latest price for rice, vegetables, fruits, etc.
- nongsan_price_history: monthly price time series
- nongsan_top_movers: biggest price changes (uptrend/downtrend)
- nongsan_search_items: find items by keyword
- wagri_fresh_market: fresh market daily prices from WAGRI API (requires auth)

Data sources:
- 農業物価統計調査 (MAFF e-Stat): monthly national average prices, 1951-present
- WAGRI 青果物市況API: daily fresh market prices by market/item (requires registration)
"""