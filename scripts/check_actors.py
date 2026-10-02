import requests, os
with open('.env') as f:
    for line in f:
        line=line.strip()
        if '=' in line and not line.startswith('#'):
            k,v=line.split('=',1)
            os.environ[k]=v
token = os.environ.get('APIFY_TOKEN','').strip()
print('token len:', len(token))

# Check if these actors exist in the account
url = f'https://api.apify.com/v2/acts?my=true&token={token}'
r = requests.get(url, timeout=30)
if r.status_code == 200:
    items = r.json().get('data',{}).get('items',[])
    for it in items:
        name = it.get('name','')
        if 'mandarake' in name or 'dlsite' in name or 'tackleberry' in name:
            print(f'  FOUND: {name} -> id={it.get("id")}')
else:
    print('Failed:', r.status_code)