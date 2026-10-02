#!/usr/bin/env python3
import os
import json
import requests
import time

token = os.environ.get("APIFY_TOKEN")
if not token:
    print("APIFY_TOKEN not set")
    exit(1)

headers = {"Authorization": f"Bearer {token}"}

# Try with query parameter
url = "https://api.apify.com/v2/acts/DKzufUSvmuXNKHeYx/builds?version=0.2"
resp = requests.post(url, headers=headers)
print(f"Query param: {resp.status_code}")
print(resp.text[:1000])