import json
with open('/mnt/d/Project2/kensho/data/revenue-daily.json') as f:
    d = json.load(f)
e = d[-1]
runs = e.get('apify_ppe_external_runs')
print('date:', e.get('date'))
print(json.dumps(runs, indent=1, ensure_ascii=False))