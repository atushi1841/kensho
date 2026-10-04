import json, os, requests
# 2026-10-04 漏洩対策: トークンはURLではなく Authorization ヘッダで送る
import os as _os, sys as _sys  # noqa: E401
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from _apify_auth import apify_get as _apify_get, apify_urlopen as _apify_urlopen, redact_secrets  # noqa: E402
env = {}
with open('/mnt/d/Project2/kensho/.env') as f:
    for line in f:
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            env[k] = v

token = env.get('APIFY_TOKEN', '').strip()
API_BASE = 'https://api.apify.com/v2'

# 1) portfolio from pay_per_event.json
ppe = json.load(open('/mnt/d/Project2/kensho/data/tmp/pay_per_event.json'))
actors_ppe = ppe['actors_ppe']
print('portfolio count:', len(actors_ppe))

# 2) PRIORITY_ACTORS from apify_store_promo.py
import re
src = open('/mnt/d/Project2/kensho/scripts/apify_store_promo.py', encoding='utf-8').read()
m = re.search(r'PRIORITY_ACTORS: list\[dict\[str, Any\]\] = \[(.*?)\]\n\n', src, re.S)
names = re.findall(r'"actual_name":\s*"([a-z0-9-]+)"', m.group(1))
print('PRIORITY_ACTORS count:', len(names))
for n in names:
    print('  ', n, actors_ppe.get(n))

# 3) APIFY_ACTOR_URLS keys
m2 = re.search(r'APIFY_ACTOR_URLS = \{(.*?)\}\n', src, re.S)
url_keys = re.findall(r'"([a-z0-9-]+)":\s*"https://apify\.com/fruitful_quintessence', m2.group(1))
print('APIFY_ACTOR_URLS count:', len(url_keys))
missing_url = [n for n in names if n not in url_keys]
print('PRIORITY without URL entry:', missing_url)

# 4) live API: owner + runs for a sample
r = _apify_get(f'{API_BASE}/users/me?token={token}', timeout=30)
owner = (r.json().get('data') or {}).get('id', '')
print('owner:', owner)

for name in ['mandarake-auction-scraper', 'dlsite-scraper', 'tackleberry-japan-fishing-tackle-scraper', 'japan-used-camera-market-scraper']:
    fb = {'mandarake-auction-scraper':'q2E37PVTg5JcGOTEn','dlsite-scraper':'6Z7tJ3plfUmAgGmbk','tackleberry-japan-fishing-tackle-scraper':'wxMskoiHMPeeH2qAJ','japan-used-camera-market-scraper':'mQaZFo6up4YZKepC3'}[name]
    rr = _apify_get(f'{API_BASE}/acts?my=true&token={token}', timeout=30)
    items = (rr.json().get('data') or {}).get('items', [])
    aid = fb
    for it in items:
        if it.get('name') == name:
            aid = it.get('id') or fb
    rr2 = _apify_get(f'{API_BASE}/acts/{aid}/runs?token={token}&desc=1&limit=1000', timeout=30)
    its = (rr2.json().get('data') or {}).get('items', [])
    ext = sum(1 for x in its if (x.get('userId') or '') != owner)
    print(f'{name}: id={aid} total_runs={len(its)} external={ext} status={rr2.status_code}')