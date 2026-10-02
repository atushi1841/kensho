#!/usr/bin/env python3
import os
import json
import requests

token = os.environ.get("APIFY_TOKEN")
if not token:
    print("APIFY_TOKEN not set")
    exit(1)

headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# First, let's check what the actor's versions look like and try to update the actor version
url = "https://api.apify.com/v2/acts/DKzufUSvmuXNKHeYx"
resp = requests.get(url, headers=headers)
print(f"GET Status: {resp.status_code}")
data = resp.json()
print(f"Actor version: {data.get('data', {}).get('versions', [{}])[0].get('versionNumber')}")
print(f"Default build: {data.get('data', {}).get('defaultRunOptions', {}).get('build')}")