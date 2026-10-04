import json, urllib.request
d = json.load(open('/mnt/d/Project2/kensho/data/revenue-daily.json'))
print('external_users:', d[-1]['apify']['external_users_total'])
try:
    r = urllib.request.urlopen('https://api.github.com/repos/atushi1841/kensho', timeout=20)
    gh = json.loads(r.read())
    print('GitHub stars:', gh.get('stargazers_count', 0))
except Exception as e:
    print('github err:', e)