#!/usr/bin/env python3
import os
import json
import requests

token = os.environ.get("APIFY_TOKEN")
if not token:
    print("APIFY_TOKEN not set")
    exit(1)

headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# Try to set defaultBuild to 0.2.2 build ID which has schemas
url = "https://api.apify.com/v2/acts/DKzufUSvmuXNKHeYx"
resp = requests.put(url, headers=headers, json={"defaultBuild": "hgIhGfDPnHMnt2sbj"})
print(f"Set defaultBuild status: {resp.status_code}")
if resp.status_code == 200:
    print("Default build updated!")
    # Now try to make public
    print("\nMaking actor public...")
    resp = requests.put(url, headers=headers, json={"isPublic": True})
    print(f"Make public status: {resp.status_code}")
    print(resp.text)
else:
    print(resp.text)