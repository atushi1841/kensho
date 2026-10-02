#!/usr/bin/env python3
import os
import json
import requests

token = os.environ.get("APIFY_TOKEN")
if not token:
    print("APIFY_TOKEN not set")
    exit(1)

headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# Set the actor's input/output to point to the schema files in version 0.1
url = "https://api.apify.com/v2/acts/DKzufUSvmuXNKHeYx"
data = {
    "input": "./input_schema.json",
    "output": "./output_schema.json"
}
resp = requests.put(url, headers=headers, json=data)
print(f"Status: {resp.status_code}")
print(resp.json())