#!/usr/bin/env python3
"""Deploy Japan Anime Figure Price Data actor to Apify using versions API - debug."""
import os
import sys
import json
import zipfile
import urllib.request
import base64
from pathlib import Path
from apify_client import ApifyClient

REPO_ROOT = Path("/mnt/d/Project2/kensho")
ACTOR_DIR = REPO_ROOT / "apify-figure-price"

def check_token() -> str:
    token = os.environ.get("APIFY_TOKEN")
    if not token:
        env_file = REPO_ROOT / ".env"
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    if line.startswith("APIFY_TOKEN="):
                        token = line.split("=", 1)[1].strip().strip('"')
                        break
    if not token:
        raise RuntimeError("APIFY_TOKEN not set. Export it or add to .env")
    return token

def deploy_actor(token: str, actor_name: str = "japan-anime-figure-price-data") -> dict:
    # Step 1: Get or create actor
    client = ApifyClient(token)
    actor_id = None
    
    # Try to find actor by listing
    all_actors = client.actors().list(limit=100)
    for a in all_actors.items:
        if a.get("name") == actor_name:
            actor_id = a["id"]
            print(f"Found actor by listing: {actor_id}")
            break
    
    if not actor_id:
        try:
            actor = client.actors()._create(resource={"name": actor_name})
            actor_id = actor["id"]
            print(f"Created new actor: {actor_id}")
        except Exception as e:
            print(f"Actor create error: {e}")
            raise RuntimeError(f"Could not find or create actor {actor_name}")

    # Step 2: Create version with SOURCE_FILES (EXCLUDING dataset - too large)
    source_files = []
    for f in ACTOR_DIR.rglob('*'):
        if f.is_file() and '__pycache__' not in f.parts:
            # Skip dataset files - they're too large for source upload
            if 'data/' in f.parts:
                print(f"Skipping large file: {f.relative_to(ACTOR_DIR)}")
                continue
            content = f.read_bytes()
            source_files.append({
                "name": str(f.relative_to(ACTOR_DIR)),
                "content": base64.b64encode(content).decode(),
                "format": "BASE64",
            })

    print(f"Source files count: {len(source_files)}")
    for sf in source_files:
        print(f"  - {sf['name']} ({len(sf['content'])} chars base64)")

    version_payload = {
        "versionNumber": "0.1",
        "sourceType": "SOURCE_FILES",
        "sourceFiles": source_files,
        "buildTag": "latest",
    }

    payload_str = json.dumps(version_payload)
    print(f"Payload size: {len(payload_str)} bytes")

    url = f"https://api.apify.com/v2/acts/{actor_id}/versions"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"}
    req = urllib.request.Request(url, data=payload_str.encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            version = json.load(resp)
        print(f"Created version: {version.get('versionNumber')} buildTag={version.get('buildTag')}")
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}")
        body = e.read().decode()
        print(f"Response body: {body[:1000]}")
        raise

    return {"actor_id": actor_id, "version": version}

def main():
    token = check_token()
    result = deploy_actor(token)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()