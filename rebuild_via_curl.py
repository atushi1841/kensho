#!/usr/bin/env python3
import os
import json
import requests

token = os.environ.get("APIFY_TOKEN")
if not token:
    print("APIFY_TOKEN not set")
    exit(1)

headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# Try to rebuild - looking at Apify API, it seems we need to provide version at top level
url = "https://api.apify.com/v2/acts/DKzufUSvmuXNKHeYx/builds"
data = {
    "version": "0.1",
    "tag": "latest",
    "waitForFinish": 120
}
resp = requests.post(url, headers=headers, json=data)
print(f"Status: {resp.status_code}")
print(json.dumps(resp.json(), indent=2))