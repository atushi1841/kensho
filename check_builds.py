#!/usr/bin/env python3
import os
import json
import requests

token = os.environ.get("APIFY_TOKEN")
if not token:
    print("APIFY_TOKEN not set")
    exit(1)

headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# Get builds list to understand the structure
url = "https://api.apify.com/v2/acts/DKzufUSvmuXNKHeYx/builds"
resp = requests.get(url, headers=headers)
print(f"GET builds Status: {resp.status_code}")
print(json.dumps(resp.json(), indent=2))