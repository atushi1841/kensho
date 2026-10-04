# kensho-kaku — Japan Sweepstakes MCP Server

Read-only MCP server exposing the kensho Japan X/Twitter sweepstakes dataset from ken-kaku.com (additional source for Kensho sweepstakes collection).

## Tools

| Tool | Description |
|------|-------------|
| `current_sweep(keyword)` | Latest sweep matching keyword (prize, brand, URL substring) |
| `sweep_history(keyword, limit=50)` | Price time series (oldest first) |
| `top_prize_movers(direction=None, limit=10)` | Biggest |delta JPY| prize value movers, optional up/down filter |

## Data

- Source: `data/accumulated.jsonl` (estimated 500+ observations, snapshot 2026-09-28)
- Source: ken-kaku.com sweepstakes collection (additional to knshow, kenshou.club, cp.meikan)
- No network, no API key, no account required

## Data Source: Apify Store

The underlying dataset is also available as a managed Apify Actor:

- **kensho-sweep-mcp** — [https://apify.com/atushi1841/acts/kensho-sweep-mcp](https://apify.com/atushi1841/acts/kensho-sweep-mcp)
  (Actor ID: `kjf9ZKQ5zWyOQxzvL`) — the parent sweepstakes dataset that includes ken-kaku.com observations

## Run

```bash
python server/server.py          # stdio MCP transport
python server/server.py --http   # streamable-http at /mcp
```

Requires `fastmcp>=3.0.0` (see `requirements.txt`).

## MCP Bundle

`manifest.json` follows the MCPB v0.4 spec. Pack with:

```bash
npx -y @anthropic-ai/mcpb pack . dist/kensho-kaku.mcpb
```

## Revenue Model

This MCP Connector follows the Kensho revenue sharing model:
- 20% to Apify (platform fee)
- PPE model continues for internal operations
- Revenue generated from external queries via Apify MCP integration

## Integration Notes

The kensho-kaku MCP Connector serves as an additional data source for the main Kensho sweepstakes collection, complementing the existing knshow.com, kenshou.club, and cp.meikan.org sources. It provides specialized coverage of the Ken-Kaku.com sweepstakes ecosystem.