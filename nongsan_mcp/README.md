# nongsan-mcp: Japanese Agricultural Market Data MCP Server

MCP (Model Context Protocol) server exposing Japanese agricultural price data from official government sources.

## Data Sources

1. **農業物価統計調査 (MAFF e-Stat)** - Monthly national average prices, ~1951-present
   - Rice (うるち玄米, もち玄米), wheat, barley, beans, vegetables, fruits, livestock, etc.
   - 123 price series, up to 2026-07 data
   - Government Standard Terms of Use 2.0 (商用利用可 with attribution)

2. **WAGRI 青果物市況情報API** - Daily fresh market prices by market/item
   - Requires free registration at wagri.naro.go.jp
   - Nationwide major wholesale markets
   - Daily updates at ~15:00 JST

## Tools (MCP)

| Tool | Description |
|------|-------------|
| `nongsan_current_price(item)` | Latest price for an item (e.g., "うるち玄米", "トマト", "キャベツ") |
| `nongsan_price_history(item, limit=24)` | Monthly time series |
| `nongsan_top_movers(months=12, direction="both", limit=10)` | Biggest price changes |
| `nongsan_search_items(keyword)` | Find items by keyword |
| `wagri_fresh_market(date, market_code?, item_code?)` | WAGRI daily fresh prices (requires auth) |

## Quick Start

```bash
# Build data cache from e-Stat Excel
python nongsan_mcp.py --build

# Run MCP stdio server
python nongsan_mcp.py --serve

# Or run HTTP server
python nongsan_mcp.py --http
```

## MCP Client Configuration

### Cursor / Claude Desktop
```json
{
  "mcpServers": {
    "nongsan-mcp": {
      "command": "python",
      "args": ["/path/to/nongsan_mcp.py", "--serve"],
      "env": {
        "WAGRI_AUTH_KEY": "your_wagri_key_if_available"
      }
    }
  }
}
```

### FastMCP Inspector
```bash
npx @modelcontextprotocol/inspector python nongsan_mcp.py --serve
```

## Smithery Deployment

```yaml
# smithery.yaml
name: nongsan-mcp
description: Japanese agricultural market price data (MAFF e-Stat + WAGRI)
repository: https://github.com/atushi1841/nongsan-mcp
homepage: https://github.com/atushi1841/nongsan-mcp
startCommand: python nongsan_mcp.py --serve
```

## Apify Actor

```json
{
  "actor.json": {
    "usesStandbyMode": true,
    "webServerMcpPath": "/mcp",
    "standbyMcpServers": ["nongsan-mcp"]
  }
}
```

## Data Attribution

```
データ出典：農林水産省 農業物価統計調査 (政府標準利用規約2.0)
データ出典：農林水産省 青果物市況情報 (政府標準利用規約2.0)
```

## License

MIT (code) / 政府標準利用規約2.0 (data)