import json, sys
d = json.load(open('/mnt/d/Project2/kensho/data/apify_ppe_external_views_state.json'))
print(json.dumps({k: type(v).__name__ for k,v in d.items()}, indent=2))
print('---')
for p,v in d.get('points',{}).items():
    print(f"Point {p}: date={v.get('point_date')}, actors={list(v.get('per_actor',{}).keys())}")