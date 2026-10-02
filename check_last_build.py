#!/usr/bin/env python3
import os
import json
import requests

token = os.environ.get("APIFY_TOKEN")
if not token:
    env_file = "/mnt/d/Project2/kensho/.env"
    with open(env_file) as f:
        for line in f:
            if line.startswith("APIFY_TOKEN=") or line.startswith("APIFY_TOKEN_DEFAULT="):
                token = line.split("=", 1)[1].strip().strip('"')
                break

headers = {"Authorization": f"Bearer {token}"}
actor_id = "DKzufUSvmuXNKHeYx"

resp = requests.get(f"https://api.apify.com/v2/actors/{actor_id}/builds?limit=1&desc=true", headers=headers)
data = resp.json()
builds = data.get("data", {}).get("items", [])
if builds:
    b = builds[0]
    print(f"Build ID: {b.get('id')} Number: {b.get('buildNumber')} Status: {b.get('status')}")
    print("actorDefinition:", json.dumps(b.get("actorDefinition"), indent=2))
    
    log_resp = requests.get(f"https://api.apify.com/v2/actor-builds/{b['id']}/log", headers=headers)
    print("--- BUILD LOG ---")
    print(log_resp.text[-2000:])
else:
    print("No builds found")