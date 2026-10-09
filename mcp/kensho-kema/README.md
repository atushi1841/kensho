# kensho-kema — Japan Sweepstakes MCP Server (ke-ma.net)

Read-only MCP server exposing the kensho Japan X/Twitter sweepstakes dataset from
ke-ma.net (懸賞マニア) — the 5th sweepstakes collection source in the Kensho pipeline.

## Tools

| Tool | Description |
|------|-------------|
| `current_sweep(keyword)` | Latest sweep matching keyword (tweet text, prize, URL substring) |
| `sweep_history(keyword, limit=50)` | Time series of matching sweeps (oldest first) |
| `top_prize_movers(direction=None, limit=10)` | Biggest \|delta JPY\| prize value movers, optional up/down filter |

## Data

- Source: `data/accumulated.jsonl` (ke-ma.net observations, snapshot 2026-10-03)
- ke-ma.net is an open sweepstakes listing site that publishes X (Twitter) URLs directly,
  so its entries are collected in a single pass (no tweet scraping required).
- No network, no API key, no account required.

## Data Source: Apify Store

The underlying dataset is also available as a managed Apify Actor:

- **kensho-sweep-mcp** — [https://apify.com/atushi1841/acts/kensho-sweep-mcp](https://apify.com/atushi1841/acts/kensho-sweep-mcp)
  (Actor ID: `kjf9ZKQ5zWyOQxzvL`) — the parent sweepstakes dataset that includes ke-ma.net observations

## Run

```bash
python server/server.py          # stdio MCP transport
```

Requires `fastmcp>=3.0.0` (see `requirements.txt`).

## MCP Bundle

`manifest.json` follows the MCPB v0.4 spec. Pack with:

```bash
python scripts/pack_mcpb.py
```

## Revenue Model

This MCP Connector follows the Kensho revenue sharing model:
- 20% to Apify (platform fee)
- PPE model continues for internal operations
- Revenue generated from external queries via Apify MCP integration

## Integration Notes

The kensho-kema MCP Connector serves as an additional data source for the main Kensho
sweepstakes collection, complementing the existing knshow.com, ken-kaku.com, kenshou.club,
and cp.meikan.org sources. It provides specialized coverage of the ke-ma.net (懸賞マニア)
sweepstakes ecosystem.

## Data Source: Apify Store & Smithery Registry

This MCP server is available on:

- **Apify Store**: [Ke-ma.net sweepstakes data](https://apify.com/fruitful_quintessence/acts/kensho-sweep-mcp) — Ke-ma.net sweepstakes data
- **Smithery Registry**: [Install via Smithery](https://server.smithery.ai/kjf9ZKQ5zWyOQxzvL) — MCP server for AI agents

Install via Smithery:
```bash
npx @smithery/cli install kjf9ZKQ5zWyOQxzvL --client claude
```
