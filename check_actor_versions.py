#!/usr/bin/env python3
import os
import json
import requests

token = os.environ.get("APIFY_TOKEN")
if not token:
    print("APIFY_TOKEN not set")
    exit(1)

headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# Check what fields are expected for build trigger
url = "https://api.apify.com/v2/acts/DKzufUSvmuXNKHeYx"
resp = requests.get(url, headers=headers)
print(f"Actor info status: {resp.status_code}")
data = resp.json().get("data", {})
print(f"Versions: {json.dumps(data.get('versions', []), indent=2)}")