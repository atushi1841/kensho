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

# Get version 0.1
version_client = actor_client.version("0.1")
version = version_client.get()
print("Version 0.1:")
print("  buildTag:", version.get("buildTag"))
print("  has inputSchema:", 'inputSchema' in version)
print("  has outputSchema:", 'outputSchema' in version)

# Get default build
default_build = actor_client.default_build(wait_for_finish=30)
print("Default build:")
build_data = default_build.get()
print("  status:", build_data.get("status"))
print("  id:", build_data.get("id"))

# Check build details
build_client = actor_client.build(build_data.get("id"))
build = build_client.get()
print("Build details:")
print("  status:", build.get("status"))
print("  finishedAt:", build.get("finishedAt"))