#!/usr/bin/env python3
import os
import json
import requests

token = os.environ.get("APIFY_TOKEN")
if not token:
    print("APIFY_TOKEN not set")
    exit(1)

headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# Try different ways to trigger a build
url = "https://api.apify.com/v2/acts/DKzufUSvmuXNKHeYx/builds"

# Try with buildTag
resp = requests.post(url, headers=headers, json={"buildTag": "latest"})
print(f"With buildTag latest: {resp.status_code}")
print(resp.text[:500])