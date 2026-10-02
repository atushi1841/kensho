#!/usr/bin/env python3
"""Deploy Japan Anime Figure Price Data actor to Apify using versions API."""
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
    # Create zip for local artifact
    zip_path = REPO_ROOT / f"{actor_name}.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file in ACTOR_DIR.rglob('*'):
            if file.is_file() and '__pycache__' not in file.parts:
                arcname = file.relative_to(ACTOR_DIR)
                zf.write(file, arcname)
    print(f"Created actor zip: {zip_path} ({zip_path.stat().st_size} bytes)")

    # Step 1: Create or get actor
    client = ApifyClient(token)
    try:
        existing = client.actor(actor_name)._get()
        if existing:
            actor_id = existing["id"]
            print(f"Actor exists: {actor_id}")
        else:
            actor = client.actors()._create(resource={"name": actor_name})
            actor_id = actor["id"]
            print(f"Created new actor: {actor_id}")
    except Exception as e:
        print(f"Actor get/create error: {e}")
        raise

    # Step 2: Create version with SOURCE_FILES
    source_files = []
    for f in ACTOR_DIR.rglob('*'):
        if f.is_file() and '__pycache__' not in f.parts:
            content = f.read_bytes()
            source_files.append({
                "name": str(f.relative_to(ACTOR_DIR)),
                "content": base64.b64encode(content).decode(),
                "format": "BASE64",
            })

    version_payload = {
        "versionNumber": "0.1",
        "sourceType": "SOURCE_FILES",
        "sourceFiles": source_files,
        "buildTag": "latest",
    }

    url = f"https://api.apify.com/v2/acts/{actor_id}/versions"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"}
    req = urllib.request.Request(url, data=json.dumps(version_payload).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        version = json.load(resp)
    print(f"Created version: {version.get('versionNumber')} buildTag={version.get('buildTag')}")

    return {"actor_id": actor_id, "version": version}

def main():
    token = check_token()
    result = deploy_actor(token)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()