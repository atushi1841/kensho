#!/usr/bin/env python3
import os
import json
import requests

token = os.environ.get("APIFY_TOKEN")
if not token:
    print("APIFY_TOKEN not set")
    exit(1)

headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# Try to update the actor's defaultRunOptions.build to point to latest successful build (0.1.35)
url = "https://api.apify.com/v2/acts/DKzufUSvmuXNKHeYx"
data = {
    "defaultRunOptions": {
        "build": "0.1.35",
        "timeoutSecs": 300,
        "memoryMbytes": 1024
    }
}
resp = requests.put(url, headers=headers, json=data)
print(f"PUT Status: {resp.status_code}")
print(json.dumps(resp.json(), indent=2))