import urllib.request, json, os
with open('/mnt/d/Project2/kensho/.env') as f:
    for line in f:
        if line.startswith('APIFY_TOKEN_DEFAULT='):
            tok = line.split('=', 1)[1].strip().strip('"')
            break
req = urllib.request.Request('https://api.apify.com/v2/acts/DKzufUSvmuXNKHeYx/builds', headers={'Authorization':'Bearer '+tok})
resp = urllib.request.urlopen(req, timeout=20)
data = json.load(resp)
for b in data.get('data', {}).get('items', []):
    print(f"Build {b.get('versionNumber')} (id={b.get('id')}) status={b.get('status')}")