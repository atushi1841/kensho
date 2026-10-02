import urllib.request, json, os
with open('/mnt/d/Project2/kensho/.env') as f:
    for line in f:
        if line.startswith('APIFY_TOKEN_DEFAULT='):
            tok = line.split('=', 1)[1].strip().strip('"')
            break
# Check build log - full
req = urllib.request.Request('https://api.apify.com/v2/acts/DKzufUSvmuXNKHeYx/builds/0.1.163/log', headers={'Authorization': 'Bearer ' + tok})
with urllib.request.urlopen(req, timeout=20) as f:
    print(f.read().decode('utf-8'))