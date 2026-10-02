#!/usr/bin/env python3
"""Deploy Japan Anime Figure Price Data actor to Apify."""
import os
import sys
import json
import zipfile
from pathlib import Path

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

def deploy_actor(token: str, actor_id: str = "DKzufUSvmuXNKHeYx") -> dict:
    # Create zip of actor directory
    zip_path = REPO_ROOT / f"japan-anime-figure-price-data.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file in ACTOR_DIR.rglob('*'):
            if file.is_file() and '__pycache__' not in file.parts:
                arcname = file.relative_to(ACTOR_DIR)
                zf.write(file, arcname)
    print(f"Created actor zip: {zip_path} ({zip_path.stat().st_size} bytes)")

    # Build source files
    source_files = []
    for f in ACTOR_DIR.rglob('*'):
        if f.is_file() and '__pycache__' not in f.parts:
            source_files.append({"name": str(f.relative_to(ACTOR_DIR)), "content": f.read_bytes()})

    try:
        from apify_client import ApifyClient
        client = ApifyClient(token)

        # Try to get existing actor by ID
        existing = client.actor(actor_id)._get()
        if existing:
            print(f"Actor exists: {existing['id']} - {existing['name']}")
        else:
            print("Actor does not exist")
            return {"error": "Actor not found"}

        # Build and deploy - try with version at top level
        build = client.actor(actor_id).builds()._create({
            "version": "0.1",
            "resource": {
                "sourceFiles": source_files,
                "tag": "latest",
                "waitForFinish": 120,
            }
        })

        print(f"Build status: {build.get('status')}")
        return {"actor_id": actor_id, "build": build}

    except Exception as e:
        print(f"Deploy error: {e}")
        raise

def main():
    token = check_token()
    result = deploy_actor(token)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()