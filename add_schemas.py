#!/usr/bin/env python3
import os
import json
import requests

token = os.environ.get("APIFY_TOKEN")
if not token:
    print("APIFY_TOKEN not set")
    exit(1)

headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# Load input and output schemas
with open('/mnt/d/Project2/kensho/apify-figure-price/input_schema.json') as f:
    input_schema = json.load(f)
with open('/mnt/d/Project2/kensho/apify-figure-price/output_schema.json') as f:
    output_schema = json.load(f)

# Update actor with schemas
url = "https://api.apify.com/v2/acts/DKzufUSvmuXNKHeYx"
data = {"input": input_schema, "output": output_schema}
resp = requests.put(url, headers=headers, json=data)
print(f"Status: {resp.status_code}")
print(resp.json())