#!/usr/bin/env python3
import os
import json
import requests

token = os.environ.get("APIFY_TOKEN")
if not token:
    print("APIFY_TOKEN not set")
    exit(1)

headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
url = "https://api.apify.com/v2/acts/DKzufUSvmuXNKHeYx"

# Make actor public
data = {"isPublic": True}
resp = requests.put(url, headers=headers, json=data)
print(f"PUT Status: {resp.status_code}")
if resp.status_code == 200:
    result = resp.json()
    print(json.dumps(result, indent=2))
else:
    print(resp.text)