#!/usr/bin/env python3
import urllib.request, json, os
from urllib import error

tok = open('/mnt/d/Project2/kensho/.env').read().split('APIFY_TOKEN_DEFAULT=')[1].splitlines()[0].strip().strip('"')
with open('/mnt/d/Project2/kensho/apify-figure-price/input_schema.json') as f:
    input_schema = json.load(f)
with open('/mnt/d/Project2/kensho/apify-figure-price/output_schema.json') as f:
    output_schema = json.load(f)

# Update the VERSION 0.1 with input/output schemas - try different field names
actor_update_url = "https://api.apify.com/v2/acts/DKzufUSvmuXNKHeYx/versions/0.1"

# Try with input/output (lowercase)
update_data = {
    "input": input_schema,
    "output": output_schema,
}
req = urllib.request.Request(
    actor_update_url,
    data=json.dumps(update_data).encode("utf-8"),
    headers={
        "Authorization": f"Bearer {tok}",
        "Content-Type": "application/json",
    },
    method="PUT",
)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        updated = json.load(resp).get("data", {})
    print("VERSION UPDATE SUCCESS")
    print('input:', 'present' if updated.get('input') else 'missing')
    print('output:', 'present' if updated.get('output') else 'missing')
except urllib.error.HTTPError as e:
    print(f"HTTP Error {e.code}: {e.reason}")
    print(e.read().decode())