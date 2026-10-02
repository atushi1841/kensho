from apify_client import ApifyClient
import json

with open('.env') as f:
    tok = f.read().split('APIFY_TOKEN_DEFAULT=')[1].splitlines()[0].strip().strip('"')
client = ApifyClient(tok)
with open('apify-figure-price/actor.json') as f:
    spec = json.load(f)
actor = client.actor('DKzufUSvmuXNKHeYx')
print('Actor get():')
print(json.dumps(actor.get(), indent=2, default=str))