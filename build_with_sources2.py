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

# Read the updated schema files
with open("/mnt/d/Project2/kensho/apify-figure-price/input_schema.json", "r") as f:
    input_schema = f.read()

with open("/mnt/d/Project2/kensho/apify-figure-price/output_schema.json", "r") as f:
    output_schema = f.read()

with open("/mnt/d/Project2/kensho/apify-figure-price/actor.json", "r") as f:
    actor_json = f.read()

# Try to build with source files included using query parameter
url = "https://api.apify.com/v2/acts/DKzufUSvmuXNKHeYx/builds?version=0.2"
data = {
    "sourceFiles": [
        {"name": "actor.json", "format": "TEXT", "content": actor_json},
        {"name": "input_schema.json", "format": "TEXT", "content": input_schema},
        {"name": "output_schema.json", "format": "TEXT", "content": output_schema}
    ]
}
resp = requests.post(url, headers=headers, json=data)
print(f"Build with source files status: {resp.status_code}")
if resp.status_code == 201:
    build_info = resp.json()
    build_id = build_info.get("data", {}).get("id")
    print(f"Build started: {build_id}")
    
    # Wait for build to complete
    print("Waiting for build to complete...")
    for i in range(60):
        time.sleep(5)
        resp = requests.get(f"https://api.apify.com/v2/actor-builds/{build_id}", headers=headers)
        if resp.status_code == 200:
            build = resp.json().get("data", {})
            status = build.get("status")
            print(f"  Status: {status}")
            if status in ("SUCCEEDED", "FAILED", "ABORTED"):
                if status == "SUCCEEDED":
                    print("Build succeeded! Setting as default build...")
                    url_default = "https://api.apify.com/v2/acts/DKzufUSvmuXNKHeYx"
                    resp = requests.put(url_default, headers=headers, json={"defaultBuild": build_id})
                    print(f"Set default build status: {resp.status_code}")
                    if resp.status_code == 200:
                        print("Default build updated!")
                        # Now try to make public
                        print("\nMaking actor public...")
                        resp = requests.put(url_default, headers=headers, json={"isPublic": True})
                        print(f"Make public status: {resp.status_code}")
                        print(resp.text)
                else:
                    print(f"Build failed: {build.get('statusMessage', 'Unknown error')}")
                break
else:
    print(resp.text)