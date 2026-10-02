import re
src=open('/mnt/d/Project2/kensho/scripts/apify_ppe_external_views.py').read()
m=re.search(r'PROMO_ACTORS: list\[dict\[str, Any\]\] = \[(.*?)\]\n', src, re.S)
names=re.findall(r'"actual_name":\s*"([a-z0-9-]+)"', m.group(1))
print(len(names))
print(names)
