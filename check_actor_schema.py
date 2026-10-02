import urllib.request, json
tok = open('.env').read().split('APIFY_TOKEN_DEFAULT=')[1].splitlines()[0].strip().strip('"')
req = urllib.request.Request('https://api.apify.com/v2/acts/DKzufUSvmuXNKHeYx', headers={'Authorization':'Bearer '+tok})
resp = urllib.request.urlopen(req, timeout=20)
data = json.load(resp)
print(json.dumps(data.get('data', {}).get('input'), indent=2))
print('---')
print(json.dumps(data.get('data', {}).get('output'), indent=2))