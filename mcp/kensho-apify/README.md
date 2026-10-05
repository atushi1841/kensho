# kensho-apify — Apify Actor MCP Server

MCP server that wraps Apify Actors for on-demand Japanese market data fetching.

## Tools

| Tool | Description |
|------|-------------|
| `list_actors()` | List all available Apify actors |
| `run_actor(actor_id, input_data, timeout_seconds)` | Run an Apify actor with input parameters |
| `get_run(run_id)` | Get run status and results |
| `get_dataset(run_id, limit)` | Fetch dataset items from a run |

## Data Sources

Japanese market data from:
- **Mercari**: 中古品価格検索
- **Yahoo Auctions**: オークション落札価格
- **Rakuten**: 楽天市場商品データ
- **Suumo**: 不動産物件情報
- **Tabelog**: レストランレビュー

## Requirements

- `APIFY_TOKEN` environment variable (from https://apify.com/account/tokens)
- Python 3.10+

## Installation (Smithery)

```bash
smithery install @atushi1841/kensho-apify
```

## More MCP Servers

- **[kensho-kaku](https://github.com/atushi1841/kensho/tree/main/mcp/kensho-kaku)** — Sweepstakes from ken-kaku.com
- **[kensho-kclub](https://github.com/atushi1841/kensho/tree/main/mcp/kensho-kclub)** — Sweepstakes from kenshou.club
- **[kensho-kema](https://github.com/atushi1841/kensho/tree/main/mcp/kensho-kema)** — Sweepstakes from ke-ma.net
- **[tcg-price-japan](https://github.com/atushi1841/kensho/tree/main/mcp/tcg-price-japan)** — TCG used-price trends

## Run

```bash
export APIFY_TOKEN=apify_api_xxx
python server.py          # stdio MCP transport
python server.py --http   # streamable-http at /mcp
```
