#!/usr/bin/env python3
import os
import json
import requests

token = os.environ.get("APIFY_TOKEN")
if not token:
    print("APIFY_TOKEN not set")
    exit(1)

headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# Just make the actor public
url = "https://api.apify.com/v2/acts/DKzufUSvmuXNKHeYx"
data = {"isPublic": True}
resp = requests.put(url, headers=headers, json=data)
print(f"Status: {resp.status_code}")
print(resp.json())