from apify_client import ApifyClient
import os

with open('.env') as f:
    tok = f.read().split('APIFY_TOKEN_DEFAULT=')[1].splitlines()[0].strip().strip('"')
client = ApifyClient(tok)
actor = client.actor('DKzufUSvmuXNKHeYx')
result = actor.get()
data = result.get('data', result)
print('isPublic:', data.get('isPublic'))
print('defaultRunBuild:', data.get('defaultRunBuild'))
versions = data.get('versions', [])
for v in versions:
    print(f"Version {v.get('versionNumber')}: input={'SET' if v.get('input') else 'null'}, output={'SET' if v.get('output') else 'null'}")