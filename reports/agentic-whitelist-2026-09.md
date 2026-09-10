# Agentic Payments / x402 Whitelist Rollout — 2026-09 (critic v87, t_370e65d0)

Date: 2026-09-10 (JST). Worker: kensho-revenue-worker, run 354.
Task: critic v87 — rollout `isWhiteListedForAgenticPayments` across 25 PPE actors.

## Result (measured, fresh re-scan 2026-09-10 ~16:00)

Success metric ACHIEVED: whitelisted count for `username=fruitful_quintessence`
is **62 / 72 public actors**, not 1 as the critic baseline claimed at 14:20.
Apify's rollout has already whitelisted all PPE actors except two MCP actors:

| Metric | Value | Evidence file |
|---|---|---|
| My public store actors | 72 | `verify_v87.json` (workspace) |
| `isWhiteListedForAgenticPayments=True` | **62** (all PAY_PER_EVENT) | `my_store_flags.json` |
| Not whitelisted | 10 (8 FREE + 2 PPE) | `notwhitelisted.json` |
| Remaining PPE gaps | `japan-market-mcp` (57SNehd4cHNFyUCj3), `mandarake-surugaya-mcp` (xUYsD13SVHHRFQS1H) | `characterize.py` output |

Flagship PPE actors (camera / watch / luxury / instrument / offmall / suumo /
goo-net / hotpepper / mercari / yahoo-auctions / dlsite / dmm / rakuten-mcp etc.)
are **already True** — the critic card's 14:20 snapshot predated (or miscounted)
the whitelist state; the 15:05 in-run scan and this 16:00 re-scan both show 62.

## Key findings

1. **No self-serve enable path via API.** `PUT /v2/acts/{id}` with
   `allowsAgenticUsers` → 400 `schema-validation: allowsAgenticUsers is not
   allowed by the updatedActor schema` (`probe.log`). The actor object and the
   `/v2/models/actor-update` schema contain no agentic/x402 fields. The flag is
   server-side (Apify-controlled) — surfaced in store items only as
   `isWhiteListedForAgenticPayments` (boolean, True or absent).
2. **Store filter works per-user.** `GET /v2/store?username=fruitful_quintessence
   &allowsAgenticUsers=true` → count=62 (matches flag scan). Community-wide the
   same filter caps `count` at 1000 — do not read it as a total.
3. **Docs pages are SPA shells** (~26 KB, no article content via plain curl);
   the earlier run's `docscan.py`/`docpages.py` probes found no whitelist
   request form text. Dashboard toggle status is unknown but API-side is
   definitively read-only.
4. **Correlation: PPE ⇒ whitelisted.** All 62 wl=True actors are PAY_PER_EVENT;
   the 8 FREE actors are False/absent. The 2 exceptions are the newer MCP-server
   PPE actors — likely invitation/rollout lag, not a structural exclusion
   (`rakuten-japan-mcp`, a PPE MCP actor, IS whitelisted).

## Procedure (for enabling future actors)

1. Publish actor with PAY_PER_EVENT pricing → whitelist appears to follow PPE
   monetization automatically on rollout waves (no request was filed by us for
   the 61 actors that flipped between 9/8 KYC pass and today).
2. Verify: `bash scripts/check_agentic_whitelist.sh` (see workspace
   `verify_v87.py` for the canonical scan) —
   `GET /v2/store?limit=1000&username=fruitful_quintessence`, count
   `isWhiteListedForAgenticPayments`.
3. If a PPE actor stays False > ~2 weeks after publish, file a request via
   Apify support / Discord #monetization with actor ID.

## Remaining follow-up

Request whitelist for the 2 PPE MCP actors (japan-market-mcp,
mandarake-surugaya-mcp) via Apify support/Discord — tracked as board follow-up
card (child of t_370e65d0).

## Artifacts

Scan scripts + JSON evidence: `~/.hermes/kanban/boards/kensho-ai-team/workspaces/t_370e65d0/`
(`verify_v87.py`, `my_store_flags.json`, `notwhitelisted.json`, `verify_v87.json`,
`community_agentic_mine.json`, `probe.log`, `keys_scan.py`, `characterize.py`).
