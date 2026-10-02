#!/usr/bin/env python3
import urllib.request, json, os
from urllib import error

tok = open('/mnt/d/Project2/kensho/.env').read().split('APIFY_TOKEN_DEFAULT=')[1].splitlines()[0].strip().strip('"')

# Try making public WITHOUT input/output - they should come from the built version
actor_update_url = "https://api.apify.com/v2/acts/DKzufUSvmuXNKHeYx"
update_data = {
    "isPublic": True,
    "defaultRunOptions": {"build": "latest"},
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
    print("SUCCESS")
    print('isPublic:', updated.get('isPublic'))
    print('input:', 'present' if updated.get('input') else 'missing')
    print('output:', 'present' if updated.get('output') else 'missing')
except urllib.error.HTTPError as e:
    print(f"HTTP Error {e.code}: {e.reason}")
    print(e.read().decode())