#!/usr/bin/env python3
import os
import json
import requests

token = os.environ.get("APIFY_TOKEN")
if not token:
    print("APIFY_TOKEN not set")
    exit(1)

headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# Read the updated schema files
with open("/mnt/d/Project2/kensho/apify-figure-price/input_schema.json", "r") as f:
    input_schema = f.read()

with open("/mnt/d/Project2/kensho/apify-figure-price/output_schema.json", "r") as f:
    output_schema = f.read()

with open("/mnt/d/Project2/kensho/apify-figure-price/actor.json", "r") as f:
    actor_json = f.read()

# Update the actor with new source files
url = "https://api.apify.com/v2/acts/DKzufUSvmuXNKHeYx"
data = {
    "sourceFiles": [
        {"name": "actor.json", "format": "TEXT", "content": actor_json},
        {"name": "input_schema.json", "format": "TEXT", "content": input_schema},
        {"name": "output_schema.json", "format": "TEXT", "content": output_schema}
    ]
}
resp = requests.put(url, headers=headers, json=data)
print(f"Update source files status: {resp.status_code}")
print(resp.text[:2000])