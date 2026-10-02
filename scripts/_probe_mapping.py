import json, re
src=open('/mnt/d/Project2/kensho/scripts/apify_store_promo.py', encoding='utf-8').read()
m=re.search(r'mapping = \{(.*?)\}\n    return mapping', src, re.S)
keys=re.findall(r'"([a-z0-9-]+)":\s*\{', m.group(1))
ppe=json.load(open('/mnt/d/Project2/kensho/data/tmp/pay_per_event.json'))['actors_ppe']
print(len(keys))
for k in keys:
    print(k, k in ppe)
