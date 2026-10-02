#!/usr/bin/env python3
import os
import json
import requests
import time

token = os.environ.get("APIFY_TOKEN")
if not token:
    print("APIFY_TOKEN not set")
    exit(1)

headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# Try using the correct Apify API - maybe need to specify actId
url = "https://api.apify.com/v2/acts/DKzufUSvmuXNKHeYx/builds"

# Try with empty body
resp = requests.post(url, headers=headers, json={})
print(f"Empty body: {resp.status_code}")
print(resp.text[:1000])