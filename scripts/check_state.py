import json
with open('data/apify_ppe_external_views_state.json') as f:
    d = json.load(f)
print(json.dumps(list(d.get('points',{}).get('168h',{}).get('per_actor',{}).keys()), indent=2))