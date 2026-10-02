#!/usr/bin/env python3
import os
import json
from apify_client import ApifyClient

token = os.environ.get("APIFY_TOKEN")
if not token:
    print("APIFY_TOKEN not set")
    exit(1)

client = ApifyClient(token)

# Get actor to verify it exists
actor = client.actor("DKzufUSvmuXNKHeYx")._get()
print(f"Actor: {actor['id']} - {actor['name']} - isPublic: {actor['isPublic']}")

# Try to rebuild using the apify_client
build = client.actor("DKzufUSvmuXNKHeYx").builds()._create({
    "resource": {
        "tag": "latest",
        "waitForFinish": 120
    }
})

print(f"Build status: {build.get('status')}")
print(json.dumps(build, indent=2))