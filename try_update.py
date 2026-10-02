#!/usr/bin/env python3
import os
import sys
sys.path.insert(0, '/mnt/d/Project2/kensho')

from scripts.deploy_figure_price_actor import check_token, deploy_actor

token = check_token()
print("Token loaded:", token[:10] + "...")

# Use the ApifyClient to just update is_public
from apify_client import ApifyClient
client = ApifyClient(token)
actor_client = client.actor("DKzufUSvmuXNKHeYx")

# First check current state
current = actor_client.get()
print("Current isPublic:", current.get("isPublic"))

# Try updating with is_public only
updated = actor_client.update(is_public=True, default_run_build="latest")
print("Updated isPublic:", updated.get("isPublic"))
print("Updated input:", 'present' if updated.get('input') else 'missing')
print("Updated output:", 'present' if updated.get('output') else 'missing')