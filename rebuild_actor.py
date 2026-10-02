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

# First, let's check what builds exist
url_builds = "https://api.apify.com/v2/acts/DKzufUSvmuXNKHeYx/builds"
resp = requests.get(url_builds, headers=headers)
print(f"Builds list status: {resp.status_code}")
if resp.status_code == 200:
    builds = resp.json()
    for b in builds.get("data", [])[:5]:
        print(f"  Build: {b.get('buildNumber')} - {b.get('status')} - finished: {b.get('finishedAt')}")
        if b.get('status') == 'SUCCEEDED':
            print(f"    Has input schema: {b.get('hasInputSchema', 'N/A')}")
            print(f"    Has output schema: {b.get('hasOutputSchema', 'N/A')}")

# Trigger a new build from the latest source (version 0.2 has schemas)
url_build = "https://api.apify.com/v2/acts/DKzufUSvmuXNKHeYx/builds"
resp = requests.post(url_build, headers=headers, json={"versionNumber": "0.2"})
print(f"\nTrigger build status: {resp.status_code}")
if resp.status_code in (200, 201):
    build_info = resp.json()
    build_id = build_info.get("data", {}).get("id")
    print(f"Build started: {build_id}")
    
    # Wait for build to complete
    print("Waiting for build to complete...")
    for i in range(60):  # up to 5 minutes
        time.sleep(5)
        resp = requests.get(f"https://api.apify.com/v2/actor-builds/{build_id}", headers=headers)
        if resp.status_code == 200:
            build = resp.json().get("data", {})
            status = build.get("status")
            print(f"  Status: {status}")
            if status in ("SUCCEEDED", "FAILED", "ABORTED"):
                if status == "SUCCEEDED":
                    print("Build succeeded! Setting as default build...")
                    # Set as default build
                    url_default = "https://api.apify.com/v2/acts/DKzufUSvmuXNKHeYx"
                    resp = requests.put(url_default, headers=headers, json={"defaultBuild": build_id})
                    print(f"Set default build status: {resp.status_code}")
                    if resp.status_code == 200:
                        print("Default build updated!")
                else:
                    print(f"Build failed: {build.get('statusMessage', 'Unknown error')}")
                break
else:
    print(resp.text)