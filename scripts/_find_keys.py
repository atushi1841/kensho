import os
os.chdir('/mnt/d/Project2/kensho')
import json
with open('scripts/apify_store_promo.py') as f:
    src=f.read()
# find mapping
import re
mapping={}
m=re.search(r'mapping = \{(.*?)\}\n    return mapping', src, re.S)
keys=re.findall(r'"([a-z0-9-]+)":\s*\{', m.group(1))
for k in keys:
    print(k)
