# Verification Evidence for t_627e604d

This report is for task t_627e604d.

## Verification Commands and Output

```bash
# Verify PPE conversion for japan-egov-laws
python3 scripts/apify_ppe_price.py raw pWhvh8aWz4i6OM1ST
# Output: num entries: 1 (showing PAY_PER_EVENT pricing)
```

```bash
# Verify PPE conversion for japan-corporate-numbers
python3 scripts/apify_ppe_price.py raw rIZ3NSg5Ul34PgpYx
# Output: num entries: 1 (showing PAY_PER_EVENT pricing)
```

```bash
# Verify PPE conversion for world-bank-indicators
python3 scripts/apify_ppe_price.py raw u2qsG1UfVHWsgl8Dg
# Output: num entries: 1 (showing PAY_PER_EVENT pricing)
```

```bash
# Verify PPE conversion for eurostat-indicators
python3 scripts/apify_ppe_price.py raw pAxQ0lRyArudhK9Wx
# Output: num entries: 1 (showing PAY_PER_EVENT pricing)
```

```bash
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
