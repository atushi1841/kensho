#!/usr/bin/env python3
import os
import json
import requests

token = os.environ.get("APIFY_TOKEN")
if not token:
    print("APIFY_TOKEN not set")
    exit(1)

headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# Update actor with defaultRunOptions pointing to version 0.1 build
url = "https://api.apify.com/v2/acts/DKzufUSvmuXNKHeYx"
data = {"defaultRunOptions": {"build": "0.1.70"}}
resp = requests.put(url, headers=headers, json=data)
print(f"Status: {resp.status_code}")
print(resp.json())