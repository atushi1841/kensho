#!/usr/bin/env python3
import os
import json
import requests

token = os.environ.get("APIFY_TOKEN")
if not token:
    print("APIFY_TOKEN not set")
    exit(1)

headers = {"Authorization": f"Bearer {token}"}

build_id = "wKB0XZkKR8Y47vRU9"
resp = requests.get(f"https://api.apify.com/v2/actor-builds/{build_id}/log", headers=headers)
print(f"Status: {resp.status_code}")
print(resp.text[:5000])