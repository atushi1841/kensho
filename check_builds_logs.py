import urllib.request, json, os
tok = None
with open('/mnt/d/Project2/kensho/.env') as f:
    for line in f:
        if line.startswith('APIFY_TOKEN_DEFAULT='):
            tok = line.split('=', 1)[1].strip().strip('"')
            break
if not tok:
    print("Token not found")
    exit(1)
# Check builds list
req = urllib.request.Request('https://api.apify.com/v2/acts/DKzufUSvmuXNKHeYx/builds?limit=10&desc=true', headers={'Authorization': 'Bearer ' + tok})
with urllib.request.urlopen(req, timeout=20) as f:
    d = json.load(f)
    for item in d.get('data', {}).get('items', []):
        bn = item.get('buildNumber')
        bid = item.get('id')
        print(f"Build {bn} (id={bid})")
        # Get log
        req2 = urllib.request.Request(f'https://api.apify.com/v2/actor-builds/{bid}/log', headers={'Authorization': 'Bearer ' + tok})
        try:
            with urllib.request.urlopen(req2, timeout=20) as f2:
                log = f2.read().decode('utf-8')
                print(log[:2000])
        except Exception as e:
            print(f"  Log error: {e}")