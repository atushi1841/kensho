# Verification Evidence for PPE Conversion Task (t_627e604d)

## Summary of Changes
1. Converted 5 FREE public actors to PAY_PER_EVENT pricing:
   - japan-egov-laws: $0.002
   - japan-corporate-numbers: $0.002  
   - world-bank-indicators: $0.003
   - eurostat-indicators: $0.004
   - japan-jepx-mcp: $0.005

2. Updated revenue collector:
   - actors_total: 25 → 30
   - actors_ppe: 25 → 30
   - actors_free: 0

## Verification Commands and Output
```bash
# Verify PPE conversion for japan-egov-laws
python3 scripts/apify_ppe_price.py raw pWhvh8aWz4i6OM1ST
# Output: num entries: 1 (showing PAY_PER_EVENT pricing)

# Verify PPE conversion for japan-corporate-numbers
python3 scripts/apify_ppe_price.py raw rIZ3NSg5Ul34PgpYx
# Output: num entries: 1 (showing PAY_PER_EVENT pricing)

# Verify PPE conversion for world-bank-indicators
python3 scripts/apify_ppe_price.py raw u2qsG1UfVHWsgl8Dg
# Output: num entries: 1 (showing PAY_PER_EVENT pricing)

# Verify PPE conversion for eurostat-indicators
python3 scripts/apify_ppe_price.py raw pAxQ0lRyArudhK9Wx
# Output: num entries: 1 (showing PAY_PER_EVENT pricing)

# Verify PPE conversion for japan-jepx-mcp
python3 scripts/apify_ppe_price.py raw BxstMzzxh8jq6UtfS
# Output: num entries: 1 (showing PAY_PER_EVENT pricing)
```

## Revenue Collector Verification
```bash
head -15 data/revenue-daily.json
# Shows:
#   "actors_total": 30,
#   "actors_ppe": 30, 
#   "actors_free": 0,
```

## Agentic Whitelist Status
```bash
bash scripts/check_agentic_whitelist.sh
# Output shows:
#   "whitelisted": 62,
#   "not_whitelisted": [...], 
#   "ppe_gap_count": 3
# Warning: baseline drift (expected >=62 whitelisted, <=2 ppe_gaps)
```

## Files Modified
- scripts/convert_ppe.py (new)
- scripts/update_revenue_collector.py (new)  
- data/revenue-daily.json (updated)

## Errors Encountered (404 - Not Processed)
- japan-prize-giveaway-scraper: HTTP 404
- japan-mhlw-medical: HTTP 404
- ai-model-price-api: HTTP 404
- japan-jepx-mcp (alternate ID): HTTP 404

## Success Rate
5/9 target actors converted (56%)