# kensho-sweep-mcp — Japan X/Twitter Sweepstakes MCP Server

Read-only MCP server exposing the kensho Japan X/Twitter sweepstakes dataset collected from knshow.com, kenshou.club, ken-kaku.com, and cp.meikan.org.

## Tools

| Tool | Description |
|---|---|
| `current_sweep(keyword)` | Latest sweep matching keyword (prize, brand, URL substring) |
| `sweep_history(keyword, limit=50)` | Price time series (oldest first) |
| `top_prize_movers(direction=None, limit=10)` | Biggest `|delta JPY|` prize value movers, optional up/down filter |

## Data

- Source: `data/accumulated.jsonl` (1133 observations, snapshot 2026-09-27)
- Sources: knshow.com, kenshou.club, ken-kaku.com, cp.meikan.org
- No network, no API key, no account required

## Data Source: Apify Store

The underlying dataset is also available as a managed Apify Actor:

- **kensho-sweep-mcp** — [https://apify.com/atushi1841/acts/kensho-sweep-mcp](https://apify.com/atushi1841/acts/kensho-sweep-mcp)
  (Actor ID: `kjf9ZKQ5zWyOQxzvL`) — same sweepstakes dataset, refreshed on a schedule

## Run

```bash
python server/server.py          # stdio MCP transport
python server/server.py --http   # streamable-http at /mcp
```

Requires `fastmcp>=3.0.0` (see `requirements.txt`).

## MCP Bundle

`manifest.json` follows the MCPB v0.4 spec. Pack with:

```bash
npx -y @anthropic-ai/mcpb pack . dist/kensho-sweep-mcp.mcpb
```