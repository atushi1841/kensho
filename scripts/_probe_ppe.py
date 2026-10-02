import json, os, urllib.request

def load_env():
    env_path = '/mnt/d/Project2/kensho/.env'
    if os.path.exists(env_path):
        with open(env_path, encoding='utf-8-sig') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, _, v = line.partition('=')
                os.environ.setdefault(k.strip(), v.strip())

load_env()
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "").strip() or os.environ.get("APIFY_TOKEN_DEFAULT", "").strip()
print("TOKEN_SET:", bool(APIFY_TOKEN))

# 1. revenue-daily latest entry
d = json.load(open('/mnt/d/Project2/kensho/data/revenue-daily.json'))
e = d[-1]
print('date:', e.get('date'))
runs = e.get('apify_ppe_external_runs')
print(json.dumps(runs, indent=1, ensure_ascii=False))

# 2. API probe
if APIFY_TOKEN:
    req = urllib.request.Request("https://api.apify.com/v2/users/me?token=" + APIFY_TOKEN,
                                 headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        owner = json.loads(r.read().decode())["data"]["id"]
    print("OWNER:", owner)
    for a in runs.get('actors', []):
        rid = a.get('run_id')
        if not rid:
            continue
        url = f"https://api.apify.com/v2/acts/{a['actor_id']}/runs/{rid}?token={APIFY_TOKEN}"
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                dd = json.loads(r.read().decode())["data"]
            print(f"{a['actual_name']}: status={dd.get('status')} userId={dd.get('userId')} "
                  f"cec={dd.get('chargedEventCounts')} startedAt={dd.get('startedAt')}")
        except Exception as ex:
            print(f"{a['actual_name']}: ERR {ex}")