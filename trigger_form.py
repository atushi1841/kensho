#!/usr/bin/env python3
import os
import json
import requests
import time

token = os.environ.get("APIFY_TOKEN")
if not token:
    print("APIFY_TOKEN not set")
    exit(1)

headers = {"Authorization": f"Bearer {token}"}  # No Content-Type, let requests set it

# Try with form data
url = "https://api.apify.com/v2/acts/DKzufUSvmuXNKHeYx/builds"
resp = requests.post(url, headers=headers, data={"version": "0.2"})
print(f"Form data: {resp.status_code}")
print(resp.text[:1000])