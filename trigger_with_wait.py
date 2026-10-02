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

# Try to trigger a new build from the 0.2 source files
# Use the actor build endpoint
url = "https://api.apify.com/v2/acts/DKzufUSvmuXNKHeYx/builds"
resp = requests.post(url, headers=headers, json={"versionNumber": "0.2", "waitForFinish": 300})
print(f"Trigger build status: {resp.status_code}")
print(resp.text[:1000])