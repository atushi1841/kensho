import json
d=json.load(open('/mnt/d/Project2/kensho/data/apify_ppe_external_views_state.json'))
print('points', list(d['points'].keys()))
for k,v in d['points'].items():
    if 'per_promo_actor' in v:
        print(k, len(v['per_promo_actor']), sum(x.get('external_views',0) for x in v['per_promo_actor'].values()))
