import requests, os
# 2026-10-04 漏洩対策: トークンはURLではなく Authorization ヘッダで送る
import os as _os, sys as _sys  # noqa: E401
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from _apify_auth import apify_get as _apify_get, apify_urlopen as _apify_urlopen, redact_secrets  # noqa: E402
with open('.env') as f:
    for line in f:
        line=line.strip()
        if '=' in line and not line.startswith('#'):
            k,v=line.split('=',1)
            os.environ[k]=v

token = os.environ.get('APIFY_TOKEN','').strip()

# Get owner id
r = _apify_get(f'https://api.apify.com/v2/users/me?token={token}', timeout=30)
owner = r.json().get('data',{}).get('id','')
print(f'owner: {owner}')

actors = [
    ("mandarake-auction-scraper", "q2E37PVTg5JcGOTEn"),
    ("dlsite-scraper", "6Z7tJ3plfUmAgGmbk"),
    ("tackleberry-japan-fishing-tackle-scraper", "wxMskoiHMPeeH2qAJ"),
]

for name, actor_id in actors:
    # Get runs
    r = _apify_get(f'https://api.apify.com/v2/acts/{actor_id}/runs?token={token}&desc=1&limit=1000', timeout=30)
    if r.status_code == 200:
        items = r.json().get('data',{}).get('items',[])
        ext = sum(1 for run in items if run.get('userId') != owner)
        total = len(items)
        print(f'{name}: external_views={ext}, total_runs={total}')
    else:
        print(f'{name}: API error {r.status_code}')