# Critic Observation Report — 2026-10-17

## Loop Health Status
- Score: 70/100
- Priority: new_proposals
- Blocked: 0
- Running: 1 (t_f54d4ff6 — 日本不動産取引データAPI)
- Ready: 5 (all kensho-worker)

## Key Findings

### 1. Revenue Conversion Gap
- **58 actors** have 30-day users (u30d>0)
- **0 actors** converted to external_runs (32 consecutive days)
- Total external_users: 0
- Total bookmarks: 0 (trust signal missing)

### 2. Language Variant Fragmentation
20 actors are language variants of 9 base names:
- camera-cn/kr (2)
- instrument-cn/kr (2)
- luxury-cn/kr (2)
- offmall-cn/kr (2)
- watch-cn/kr (2)
- goo-net-car-scraper-es/pt/fr/ru (4)
- japan-property-market-cn/kr (2)
- japan-rent-market-cn/kr (2)
- kimono-market-cn/kr (2)

Each variant gets ~1 user, but consolidated would get ~2-4 users per base.

### 3. MCP Registry Status
- 13 servers registered in official MCP registry
- 0 listings on mcp.so, Glama.ai, LobeHub (manual submission required)
- Manual submission blocked by auth requirements

### 4. Script Bug: APIFY_TOKEN Loading
`scripts/apify_make_private.py` fails with HTTP 401:
- Script looks for `APIFY_TOKEN` env var
- `.env` has `APIFY_TOKEN_DEFAULT` (different name)
- Need to fix env var name or add fallback

## Proposal Created
- **Task ID**: t_816229c1
- **Title**: Apify语言版actor一括非公開化で人気シグナル統合
- **Assignee**: kensho-revenue-worker
- **Priority**: 2 (medium)
- **Idempotency Key**: critic-20261017-v2-language-concat

## Proposed Actions (Future)
1. Fix APIFY_TOKEN loading in apify_make_private.py
2. Add MCP directory submission automation (mcp.so/Glama/LobeHub)
3. Add review request workflow for high-use actors (requires user X post)
4. Consolidate language variants to single canonical actors

## Additional Findings (2026-10-17 2nd run)

### 1. Store Invisibility Confirmed (v90 Replication)
- Anonymous store search: total=72 items=0 (v90 finding reproduced)
- Authenticated: total=72 items=5 (token required to see own actors)
- Actor search works: `/v2/actors?search=japan` returns 81/83 mine
- Conclusion: isPublic=true ≠ Store listing. Two separate flags.

### 2. GitHub Presence Missing
- GitHub user `atsu1841`: HTTP 404 (does not exist)
- Search `kensho apify`: finds 3 repos (kensho-assets, japan-hotpepper-scraper, kimono-market-scraper)
- GITHUB_TOKEN not in .env (read-only PAT only)
- Missing trust signal for external users

### 3. Social Proof Zero
- Total reviews across 81 actors: 0
- Total bookmarks across 81 actors: 0
- Top competitors: 10-50 reviews, 100-500 bookmarks
- Review/bookmark acquisition requires manual user outreach

### 4. Previous Task Validation
- t_443551e0 (v90): archived without completing success criteria
- Was supposed to verify: `curl | items|length >= 1`
- Should have been: blocked + 【要ユーザー対応】comment instead of archive
- Lesson: archive = permanent loss of work; use blocked for manual-wait

## Proposal: GitHub Organization + Apify Actor Code Repo

**Success metric**: GitHub repo >= 1, README Apify links >= 5, repo stars >= 1 (30d)

**Verification command**:
```bash
curl -s https://api.github.com/users/atsu1841/repos | python3 -c "import json,sys; print(len(json.load(sys.stdin)))"
# Expected: >= 1
```

**Fallback**: If GitHub creation blocked, increase dev.to publishing (29 articles existing, add Apify links to all)

## Notes for Next Run
- external_runs=0 continues (32+ days)
- ready queue has 5 kensho-worker tasks waiting
- running task t_f54d4ff6 has been active for 5.5h
- Unpushed commits: 2 (git push 403 - PAT write needed)
- GitHub @atsu1841 does not exist — need to create or use existing org
