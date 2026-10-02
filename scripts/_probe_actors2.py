import json, re

# Load pay_per_event actors
ppe = json.load(open('/mnt/d/Project2/kensho/data/tmp/pay_per_event.json'))
actors_ppe = set(ppe['actors_ppe'].keys())

# Load apify_store_promo.py and extract all actors from mapping
src = open('/mnt/d/Project2/kensho/scripts/apify_store_promo.py', encoding='utf-8').read()
m = re.search(r'mapping = \{(.*?)\}\n    return mapping', src, re.S)
mapping_keys = re.findall(r'"([a-z0-9-]+)":\s*\{', m.group(1))
print('display mapping actors:', len(mapping_keys))
for k in mapping_keys:
    in_ppe = k in actors_ppe
    print(f'  {k} - PPE: {in_ppe}')

# Also check APIFY_ACTOR_URLS
m2 = re.search(r'APIFY_ACTOR_URLS = \{(.*?)\}\n', src, re.S)
url_keys = re.findall(r'"([a-z0-9-]+)":\s*"https://apify\.com/fruitful_quintessence', m2.group(1))
print('\nAPIFY_ACTOR_URLS actors:', len(url_keys))

# PRIORITY_ACTORS
m3 = re.search(r'PRIORITY_ACTORS: list\[dict\[str, Any\]\] = \[(.*?)\]\n\n', src, re.S)
priority_names = re.findall(r'"actual_name":\s*"([a-z0-9-]+)"', m3.group(1))
print('\nPRIORITY_ACTORS:', len(priority_names))
for k in priority_names:
    in_ppe = k in actors_ppe
    print(f'  {k} - PPE: {in_ppe}')

# Union of all promo-capable actors (has URL + PPE)
promo_actors = set(url_keys) & actors_ppe
print('\nUnion (URL + PPE):', len(promo_actors))
for k in sorted(promo_actors):
    print(f'  {k}')