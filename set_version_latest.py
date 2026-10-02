#!/usr/bin/env python3
import os
import sys
sys.path.insert(0, '/mnt/d/Project2/kensho')

from apify_client import ApifyClient

token = os.environ.get("APIFY_TOKEN") or os.environ.get("APIFY_TOKEN_DEFAULT")
if not token:
    with open('/mnt/d/Project2/kensho/.env') as f:
        for line in f:
            if line.startswith("APIFY_TOKEN=") or line.startswith("APIFY_TOKEN_DEFAULT="):
                token = line.split("=", 1)[1].strip().strip('"')
                break

client = ApifyClient(token)
actor_client = client.actor("DKzufUSvmuXNKHeYx")

# Update version 0.1 with build_tag="latest"
version_client = actor_client.version("0.1")
result = version_client.update(build_tag="latest")
print("Version update:", result)