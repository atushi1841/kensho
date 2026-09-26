# tcg-price-japan — Japan TCG Used-Price MCP Server

Read-only MCP server exposing the kensho Japan TCG (Pokemon / trading card)
used-price dataset collected from suruga-ya.jp.

## Tools

| Tool | Description |
|---|---|
| `tcg_current_price(item)` | Latest used/new/list price snapshot (JPY) for an item |
| `tcg_price_history(item, limit=50)` | Price time series (oldest first) |
| `tcg_top_movers(direction, limit=10)` | Biggest `\|delta JPY\|` movers, optional up/down filter |

## Data

- Source: `data/accumulated.jsonl` (960 observations, snapshot 2026-09-21)
- Marketplace: suruga-ya.jp
- No network, no API key, no account required

## Run

```bash
python server/server.py          # stdio MCP transport
python server/server.py --http   # streamable-http at /mcp
```

Requires `fastmcp>=3.0.0` (see `requirements.txt`).

## MCP Bundle

`manifest.json` follows the MCPB v0.4 spec. Pack with:

```bash
npx -y @anthropic-ai/mcpb pack . dist/tcg-price-japan.mcpb
```
