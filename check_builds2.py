import urllib.request, json, os
with open('/mnt/d/Project2/kensho/.env') as f:
    for line in f:
        if line.startswith('APIFY_TOKEN_DEFAULT='):
            tok = line.split('=', 1)[1].strip().strip('"')
            break
# Check builds
req = urllib.request.Request('https://api.apify.com/v2/acts/DKzufUSvmuXNKHeYx/builds?limit=5&desc=true', headers={'Authorization': 'Bearer ' + tok})
with urllib.request.urlopen(req, timeout=20) as f:
    d = json.load(f)
    for item in d.get('data', {}).get('items', []):
        bn = item.get('buildNumber')
        ad = item.get('actorDefinition') or {}
        print(f"Build {bn}: input={'present' if ad.get('input') else 'missing'} output={'present' if ad.get('output') else 'missing'}")
        if ad.get('input'):
            print(f"  input keys: {list(ad.get('input', {}).keys())[:5]}")
        if ad.get('output'):
            print(f"  output keys: {list(ad.get('output', {}).keys())[:5]}")