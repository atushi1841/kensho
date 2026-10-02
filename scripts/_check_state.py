import json
with open('/mnt/d/Project2/kensho/data/apify_settle_state.json') as f:
    s = json.load(f)
print('=== latest entry ===')
print(json.dumps(s['latest'], indent=1, ensure_ascii=False))