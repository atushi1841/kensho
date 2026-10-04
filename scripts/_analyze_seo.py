import json
from collections import Counter
d = json.load(open('/mnt/d/Project2/kensho/reports/apify-seo-full/apify-seo-full-2026-10-04.json'))
print('total:', len(d))
c = Counter(r['status'] for r in d)
print('statuses:', dict(c))
applied = [r for r in d if r['status'] == 'applied']
print('applied:', len(applied))
failed = [r for r in d if r['status'] == 'failed']
print('failed:', len(failed))
for f in failed[:5]:
    print('  FAIL:', f['name'], f.get('http_code'))
