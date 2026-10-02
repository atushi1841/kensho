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
resp = requests.get(url, headers=headers)
print(f"Status: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    print(json.dumps(data, indent=2))
else:
    print(resp.text)